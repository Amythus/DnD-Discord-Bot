import re
import json
import httpx
from typing import Dict, List, Optional
from pydantic import BaseModel
from google import genai
from google.genai import types

from config.settings import settings
from database.models.identity.character import Character

# Uses lowercase field as fixed in settings.py
client = genai.Client(api_key=settings.gemini_api_key)

class DDBParsedCharacter(BaseModel):
    """
    The clean LLM response DTO used by Gemini to extract D&D Beyond data.
    This avoids passing PydanticObjectId and throws no JsonSchema errors.
    """
    name: str
    race: str
    classes: Dict[str, int]
    level: int
    max_hp: int
    total_hit_dice: Dict[str, int]
    stats: Dict[str, int]
    total_spell_slots: Dict[str, int]
    inventory: List[str]
    proficiencies: List[str]

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
        
        # 2. Let Gemini parse it using the safe DTO (No PydanticObjectIds here!)
        response = client.models.generate_content(
            model='gemini-3.1-flash-lite',
            contents=f"Extract the character sheet from this JSON data: {json.dumps(raw_ddb_json)}",
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=DDBParsedCharacter,
            ),
        )
        
        parsed_data = response.parsed
        if not parsed_data:
            raise RuntimeError("Gemini failed to generate a structured parsed response.")
            
        # 3. Construct the actual Beanie Document by injecting the missing context fields
        new_character = Character(
            # --- Bot & Identity Fields (Missing from DDB) ---
            discord_user_id=discord_user_id,
            dndb_character_id=character_id,
            dndb_uri=dndb_url,
            heroic_inspiration=False,  # Default baseline state
            campaign_id=None,
            
            # --- Persistent Base Stats (From Gemini) ---
            name=parsed_data.name,
            race=parsed_data.race,
            classes=parsed_data.classes,
            level=parsed_data.level,
            max_hp=parsed_data.max_hp,
            total_hit_dice=parsed_data.total_hit_dice,
            stats=parsed_data.stats,
            total_spell_slots=parsed_data.total_spell_slots,
            inventory=parsed_data.inventory,
            proficiencies=parsed_data.proficiencies,
            model_config = ConfigDict(extra="forbid")
        )
        
        # 4. Upsert to Global Tracker (MongoDB) to prevent mid-week duplicate sync rows
        existing_char = await Character.find_one(Character.dndb_character_id == character_id)
        if existing_char:
            new_character.id = existing_char.id
            await new_character.replace()
        else:
            await new_character.save()
            
        return new_character