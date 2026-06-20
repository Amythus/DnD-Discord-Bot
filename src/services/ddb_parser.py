import re
import json
import httpx
import asyncio
from typing import Optional
from google.genai import types

# Import your centralized services
from services.gemini_client import gemini_service
from services.template_service import TemplateService

# Your database model dependency
from database.models.identity.character import Character 


class DDBParserService:
    @staticmethod
    def extract_id_from_url(url: str) -> Optional[str]:
        # """Robust ID Extraction: Extracts the character ID safely from a full URL or flat integer input."""
        # match = re.search(r'(\d+)$', url)
        # return match.group(1) if match else (url if url.isdigit() else None)
        
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
        character_id = DDBParserService.extract_id_from_url(dndb_url)
        if not character_id:
            raise ValueError("Invalid D&D Beyond URL or Character ID.")
        
        # 1. Fetch raw character context data from the endpoint
        raw_ddb_json = await DDBParserService.fetch_ddb_data(character_id)
        
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
        db_stats = {k: stats_data.get(k, 10) for k in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]}

        spell_slots_data = parsed_json.get("total_spell_slots", {})
        db_spell_slots = {str(i): spell_slots_data[f"level_{i}"] for i in range(1, 10) if spell_slots_data.get(f"level_{i}", 0) > 0}

        db_classes = {}
        for cls_str in parsed_json.get("classes", []):
            parts = cls_str.rsplit(' ', 1)
            if len(parts) == 2 and parts[1].isdigit():
                db_classes[parts[0]] = int(parts[1])

        db_hit_dice = {}
        for hd_str in parsed_json.get("total_hit_dice", []):
            if 'd' in hd_str:
                num, die = hd_str.split('d', 1)
                if num.isdigit() and die.isdigit():
                    db_hit_dice[f"d{die}"] = int(num)

        # --- Dynamic Keyword Mapping Construction ---
        insert_kwargs = {
            "discord_user_id": discord_user_id,
            "heroic_inspiration": False,
            "campaign_id": None,
            "name": parsed_json.get("name", "Unknown Character"),
            "race": parsed_json.get("race", "Unknown Race"),
            "classes": db_classes,
            "level": parsed_json.get("level", 1),
            "max_hp": parsed_json.get("max_hp", 10),
            "armor_class": parsed_json.get("armor_class", 10),
            "speed": parsed_json.get("speed", 30),
            "passive_perception": parsed_json.get("passive_perception", 10),
            "total_hit_dice": db_hit_dice,
            "stats": db_stats,
            "total_spell_slots": db_spell_slots,
            "inventory": parsed_json.get("inventory", []),
            "proficiencies": parsed_json.get("proficiencies", {})
        }

        # Handle field alias fallback between dndb_character_id vs dnd_beyond_character_id
        target_field = "dndb_character_id" if hasattr(Character, "dndb_character_id") else "dnd_beyond_character_id"
        insert_kwargs[target_field] = character_id
        insert_kwargs["dndb_uri"] = dndb_url

        existing_char = await Character.find_one({target_field: character_id})
        new_character = Character(**insert_kwargs)

        if existing_char:
            new_character.id = existing_char.id
            await new_character.replace()
        else:
            await new_character.save()
            
        return new_character
