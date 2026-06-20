import re
import json
import httpx
from typing import List, Optional
from google import genai
from google.genai import types

from config.settings import settings
from database.models.identity.character import Character

# Uses lowercase field as fixed in settings.py
client = genai.Client(api_key=settings.gemini_api_key)

# -------------------------------------------------------------
# Native Schema definition for flawless Gemini execution
# -------------------------------------------------------------
CHAR_RESPONSE_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "name": types.Schema(type=types.Type.STRING),
        "race": types.Schema(type=types.Type.STRING),
        "classes": types.Schema(
            type=types.Type.ARRAY, 
            items=types.Schema(type=types.Type.STRING),
            description="List of classes with levels, e.g. ['Fighter 3', 'Wizard 1']"
        ),
        "level": types.Schema(type=types.Type.INTEGER),
        "max_hp": types.Schema(type=types.Type.INTEGER),
        "armor_class": types.Schema(type=types.Type.INTEGER, description="Character's total base armor class"),
        "speed": types.Schema(type=types.Type.INTEGER, description="Character's walking speed in feet"),
        "passive_perception": types.Schema(type=types.Type.INTEGER, description="Character's passive Wisdom (Perception) score"),
        "total_hit_dice": types.Schema(
            type=types.Type.ARRAY, 
            items=types.Schema(type=types.Type.STRING),
            description="List of total hit dice, e.g. ['3d10', '1d6']"
        ),
        "stats": types.Schema(
            type=types.Type.OBJECT,
            properties={
                "strength": types.Schema(type=types.Type.INTEGER),
                "dexterity": types.Schema(type=types.Type.INTEGER),
                "constitution": types.Schema(type=types.Type.INTEGER),
                "intelligence": types.Schema(type=types.Type.INTEGER),
                "wisdom": types.Schema(type=types.Type.INTEGER),
                "charisma": types.Schema(type=types.Type.INTEGER),
            },
            required=["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]
        ),
        "total_spell_slots": types.Schema(
            type=types.Type.OBJECT,
            properties={
                "level_1": types.Schema(type=types.Type.INTEGER),
                "level_2": types.Schema(type=types.Type.INTEGER),
                "level_3": types.Schema(type=types.Type.INTEGER),
                "level_4": types.Schema(type=types.Type.INTEGER),
                "level_5": types.Schema(type=types.Type.INTEGER),
                "level_6": types.Schema(type=types.Type.INTEGER),
                "level_7": types.Schema(type=types.Type.INTEGER),
                "level_8": types.Schema(type=types.Type.INTEGER),
                "level_9": types.Schema(type=types.Type.INTEGER),
            },
            required=[f"level_{i}" for i in range(1, 10)]
        ),
        "inventory": types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING)),
        "proficiencies": types.Schema(
            type=types.Type.OBJECT,
            properties={
                "skills": types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING)),
                "tools": types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING)),
                "languages": types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING)),
                "weapons": types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING)),
                "armor": types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING))
            },
            required=["skills", "tools", "languages", "weapons", "armor"]
        ),
    },
    required=[
        "name", "race", "classes", "level", "max_hp", 
        "armor_class", "speed", "passive_perception",
        "total_hit_dice", "stats", "total_spell_slots", 
        "inventory", "proficiencies"
    ],
)

class DDBParserService:
    @staticmethod
    def extract_id_from_url(url: str) -> Optional[str]:
        """Robust ID Extraction: Extracts the character ID safely from a full URL or flat integer input."""
        match = re.search(r'(\d+)$', url)
        if match:
            return match.group(1)
        return url if url.isdigit() else None

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
        
        # 1. Fetch raw JSON from D&D Beyond
        raw_ddb_json = await DDBParserService.fetch_ddb_data(character_id)
        
        # 2. Query Gemini via SDK native constraints
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
        
        # 3. Process structural map transformations back to expected DB fields
        stats_data = parsed_json.get("stats", {})
        db_stats = {
            "strength": stats_data.get("strength", 10),
            "dexterity": stats_data.get("dexterity", 10),
            "constitution": stats_data.get("constitution", 10),
            "intelligence": stats_data.get("intelligence", 10),
            "wisdom": stats_data.get("wisdom", 10),
            "charisma": stats_data.get("charisma", 10)
        }

        spell_slots_data = parsed_json.get("total_spell_slots", {})
        db_spell_slots = {}
        for i in range(1, 10):
            val = spell_slots_data.get(f"level_{i}", 0)
            if val > 0:
                db_spell_slots[str(i)] = val

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

        # 4. Construct the instantiation parameters
        # FIX Note: If your actual character model uses alternative attribute names 
        # (e.g. dnd_beyond_character_id instead of dndb_character_id), adjust these targets.
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

        # Safe dynamic keyword assignment to sidestep variable name mismatches
        if hasattr(Character, "dndb_character_id"):
            insert_kwargs["dndb_character_id"] = character_id
            insert_kwargs["dndb_uri"] = dndb_url
            # FIX: Fallback to standard dict syntax lookup to prevent Beanie attribute exceptions
            existing_char = await Character.find_one({"dndb_character_id": character_id})
        else:
            # Fallback handling in case field is named dnd_beyond_character_id inside character.py
            insert_kwargs["dnd_beyond_character_id"] = character_id
            insert_kwargs["dndb_uri"] = dndb_url
            existing_char = await Character.find_one({"dnd_beyond_character_id": character_id})

        new_character = Character(**insert_kwargs)

        # 5. Execute Database Handshake
        if existing_char:
            new_character.id = existing_char.id
            await new_character.replace()
        else:
            await new_character.save()
            
        return new_character