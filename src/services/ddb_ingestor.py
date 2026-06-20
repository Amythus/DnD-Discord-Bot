import re
import json
import httpx
import asyncio
import datetime

from typing import Optional
from google.genai import types

# Import your centralized services
from services.gemini_client import gemini_service
from services.template_service import TemplateService

# Your database model dependency
from database.models.identity.character import Character 


class DDBIngestorService:
    @staticmethod
    def extract_id_from_url(url: str) -> Optional[str]: 
        """
        Robust ID Extraction: Extracts the character ID safely from a full URL, 
        even if it includes trailing slug hashes (e.g., /nXz4Zb), or a flat integer input.
        """
        match = re.search(r'/characters/(\d+)', url) or re.search(r'(\d+)', url)
        return match.group(1) if match else (url if url.isdigit() else None)

    @staticmethod
    async def fetch_ddb_data(character_id: str) -> dict:
        """Fetches the raw structured JSON sheet from the D&D Beyond Character API."""
        url = f"https://character-service.dndbeyond.com/character/v5/character/{character_id}"
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(url)
            response.raise_for_status()
            return response.json()

    @staticmethod
    async def import_character(dndb_url: str, discord_user_id: int) -> Character:
        character_id = DDBIngestorService.extract_id_from_url(dndb_url)
        if not character_id:
            raise ValueError("Invalid D&D Beyond URL or Character ID.")
        
        # 1. Fetch raw character context data from the endpoint
        raw_ddb_json = await DDBIngestorService.fetch_ddb_data(character_id)
        
        # 2. Leverage your centralized TemplateService to resolve paths and build schemas

        template_engine = TemplateService(templates_dir="templates")
        
        # Extract the schema definitions safely through your engine
        raw_schema_string = template_engine.render_prompt(
            "char_schema.json.jinja", 
            raw_character_data=json.dumps(raw_ddb_json)
        )
        
        # Parse it out into a dictionary structure and validate it into an SDK-compliant Schema object
        schema_dict = json.loads(raw_schema_string)
        validated_api_schema = types.Schema.model_validate(schema_dict)

        # 3. Pull the internal raw Gemini client
        raw_client = gemini_service.get_client()

        # 4. Offload the synchronous SDK blocking generation request into an async worker thread
        def _call_gemini_api():
            return raw_client.models.generate_content(
                model=gemini_service.model_name, # Managed dynamically via your GeminiService wrapper
                contents=f"Extract the character sheet from this JSON data: {json.dumps(raw_ddb_json)}",
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=validated_api_schema, # Passing down the hydrated SDK Schema object
                ),
            )

        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, _call_gemini_api)
        
        if not response.text:
            raise RuntimeError("Gemini failed to generate a structured parsed response.")
            
        # Clean potential markdown block pollution before evaluating JSON
        parsed_json = template_engine.clean_json_response(response.text)
        
        # --- Map Transformations ---
        stats_data = parsed_json.get("stats", {})
        db_stats = {
            "strength": stats_data.get("strength", 10),
            "dexterity": stats_data.get("dexterity", 10),
            "constitution": stats_data.get("constitution", 10),
            "intelligence": stats_data.get("intelligence", 10),
            "wisdom": stats_data.get("wisdom", 10),
            "charisma": stats_data.get("charisma", 10),
        }

        # Simplified: Spell slots directly output string keys like {"1": 4} inside schema
        db_spell_slots = {
            str(k): int(v) 
            for k, v in parsed_json.get("total_spell_slots", {}).items() 
            if int(v or 0) > 0
        }

        # Map classes back to a nested dictionary array safely
        db_classes = {}
        for cls_str in parsed_json.get("classes", []):
            parts = cls_str.rsplit(' ', 1)
            if len(parts) == 2 and parts[1].isdigit():
                db_classes[parts[0].lower()] = int(parts[1])

        # Hydrate array strings like ["3d8", "1d10"] cleanly into {"d8": 3, "d10": 1}
        db_hit_dice = {}
        for hd_str in parsed_json.get("total_hit_dice", []):
            if 'd' in hd_str:
                num, die = hd_str.split('d', 1)
                if num.isdigit() and die.isdigit():
                    db_hit_dice[f"d{die}"] = int(num)

        # Directly unpack parsed structural sub-objects or fallback to defaults
        prof_data = parsed_json.get("proficiencies", {})

        # --- Construct Clean Keyword Dictionary Arguments ---
        insert_kwargs = {
            "name": parsed_json.get("name", "Unknown Hero"),
            "race": parsed_json.get("race", "Unknown Race"),
            "classes": db_classes,
            "level": parsed_json.get("level", 1),
            "max_hp": parsed_json.get("max_hp", 10),
            "armor_class": parsed_json.get("armor_class", 10),
            "initiative_modifier": parsed_json.get("initiative_modifier", 0),
            "speed": parsed_json.get("speed", 30),
            "passive_perception": parsed_json.get("passive_perception", 10),
            "passive_investigation": parsed_json.get("passive_investigation", 10),
            "passive_insight": parsed_json.get("passive_insight", 10),
            "stats": db_stats,
            "proficiencies": {
                "saving_throws": prof_data.get("saving_throws", []),
                "skills": prof_data.get("skills", []),
                "expertise": prof_data.get("expertise", []),
                "weapons": prof_data.get("weapons", []),
                "armor": prof_data.get("armor", []),
                "tools": prof_data.get("tools", []),
                "languages": prof_data.get("languages", [])
            },
            "feats": parsed_json.get("feats", []),
            "passive_features": parsed_json.get("passive_features", []),
            "total_spell_slots": db_spell_slots,
            "total_hit_dice": db_hit_dice,
            "known_spells": parsed_json.get("known_spells", []),
            "inventory_slugs": parsed_json.get("inventory_slugs", []),
            "attuned_items": parsed_json.get("attuned_items", []),
            "gold_pieces": float(parsed_json.get("gold_pieces", 0.0)),
            "last_synced_at": datetime.datetime.now(datetime.timezone.utc)
        }

        # Beanie document search query block (Matches schema unique indexing requirements)
        existing_char = await Character.find_one({"discord_user_id": discord_user_id})
        
        if existing_char:
            # Transfer baseline key IDs before running replacements
            new_character = Character(id=existing_char.id, character_id=existing_char.character_id, **insert_kwargs)
            await new_character.replace()
        else:
            new_character = Character(**insert_kwargs)
            await new_character.save()
            
        return new_character
