import re
import json
import httpx
from pathlib import Path
from typing import List, Optional
from jinja2 import Template
from google import genai
from google.genai import types

from config.settings import settings
from database.models.identity.character import Character

client = genai.Client(api_key=settings.gemini_api_key)

# -------------------------------------------------------------
# Dynamic Schema Bootstrapping via Jinja2 File Compacting
# -------------------------------------------------------------
TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "char_schema.json.j2"
with open(TEMPLATE_PATH, "r") as f:
    schema_template = Template(f.read())

# Render template and convert stringified JSON back into a native dict
rendered_schema_dict = json.loads(schema_template.render())

# Hydrate the raw dictionary definition straight into an SDK Schema Instance
CHAR_RESPONSE_SCHEMA = types.Schema.model_validate(rendered_schema_dict)


class DDBParserService:
    @staticmethod
    def extract_id_from_url(url: str) -> Optional[str]:
        """Robust ID Extraction: Extracts the character ID safely from a full URL or flat integer input."""
        match = re.search(r'(\d+)$', url)
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
        
        raw_ddb_json = await DDBParserService.fetch_ddb_data(character_id)
        
        response = client.models.generate_content(
            model='gemini-3.1-flash-lite',
            contents=f"Extract the character sheet from this JSON data: {json.dumps(raw_ddb_json)}",
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=CHAR_RESPONSE_SCHEMA,
            ),
        )
        
        if not response.text:
            raise RuntimeError("Gemini failed to generate a structured parsed response.")
            
        parsed_json = json.loads(response.text)
        
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