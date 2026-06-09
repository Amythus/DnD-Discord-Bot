import os
import re
import json
import httpx
from typing import Optional
from google import genai
from google.genai import types

from config.settings import settings
from database.models import CharacterSheet, CharacterVitals, CharacterProficiencies, InventoryItem, SpellSlots
from services.game_engine import game_engine

class DDBParserService:
    """
    Fetches raw, highly-nested character sheets directly from D&D Beyond's backend endpoints,
    uses Gemini Structured Outputs to cleanly flatten the messy JSON payload, and formats
    the final object fields so they map precisely into your Beanie MongoDB schemas.
    """
    def __init__(self):
        # Bind the official Google AI Studio client engine
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model_name = "gemini-3.1-flash-lite"

    @staticmethod
    def extract_character_id(url: str) -> str:
        """Parses the unique numeric character ID out of a standard DDB sheet link."""
        # Matches URLs like: ://dndbeyond.com or ://dndbeyond.com
        match = re.search(r'characters/(\d+)', url)
        if not match:
            raise ValueError("Invalid D&D Beyond URL format. Unable to isolate character ID.")
        return match.group(1)

    async def fetch_raw_ddb_json(self, character_id: str) -> dict:
        """Hits D&D Beyond's proxy character data proxy endpoint to extract the internal data array."""
        # This proxy endpoint returns the full, deep character dictionary layer used by digital sheets
        proxy_url = f"https://dndbeyond.com{character_id}"
        
        # Use an async HTTP client to ensure your Discord bot gateway never halts or lags during fetch
        async with httpx.AsyncClient(timeout=15.0) as http_client:
            response = await http_client.get(proxy_url)
            if response.status_code != 200:
                raise RuntimeError(f"D&D Beyond server rejected data request. Status: {response.status_code}. Verify sheet is Public.")
            
            payload = response.json()
            # DDB wraps the core payload inside a top-level 'data' envelope key
            if "data" not in payload:
                raise ValueError("Unexpected payload envelope received from D&D Beyond backend.")
            return payload["data"]

    async def parse_and_sync_character(self, channel_id: str, player_id: str, ddb_url: str) -> Optional[CharacterSheet]:
        """
        Executes the full ingestion pipeline: extracts ID, pulls raw nested cloud data, 
        leverages Gemini to flatten the variables into type-safe formats, applies rules math,
        and saves the resulting document profile state cleanly into MongoDB.
        """
        try:
            # 1. Fetch remote raw dataset strings
            char_id = self.extract_character_id(ddb_url)
            raw_data = await self.fetch_raw_ddb_json(char_id)

            # Convert the dict to a string token frame to pass to Gemini
            json_dump_str = json.dumps(raw_data)

            # 2. Instruct Gemini to act as a Smart Parser using a Type-Safe JSON Schema mapping
            # This mapping forces the LLM to extract dirty nested objects into clear arrays
            extraction_prompt = (
                "You are an expert data migration utility. Your task is to analyze the raw, nested "
                "D&D Beyond character JSON dump and map its core attributes directly into the specified "
                "flat JSON structure. Pay close attention to extracting true baseline maximum hit points, "
                "Armor Class, and individual proficiency tier flags (0=None, 1=Proficient, 2=Expertise) for skills."
            )

            # Define the schema contract matching your model fields byte-for-byte
            gemini_response_schema = {
                "type": "OBJECT",
                "properties": {
                    "character_name": {"type": "STRING"},
                    "race": {"type": "STRING"},
                    "class_and_level": {"type": "STRING"},
                    "level": {"type": "INTEGER"},
                    "base_max_hp": {"type": "INTEGER"},
                    "base_ac": {"type": "INTEGER"},
                    "speed": {"type": "INTEGER"},
                    "stats": {
                        "type": "OBJECT",
                        "properties": {
                            "strength": {"type": "INTEGER"}, "dexterity": {"type": "INTEGER"},
                            "constitution": {"type": "INTEGER"}, "intelligence": {"type": "INTEGER"},
                            "wisdom": {"type": "INTEGER"}, "charisma": {"type": "INTEGER"}
                        },
                        "required": ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]
                    },
                    "proficiencies": {
                        "type": "OBJECT",
                        "properties": {
                            "saving_throws": {
                                "type": "OBJECT",
                                "properties": {
                                    "STR": {"type": "BOOLEAN"}, "DEX": {"type": "BOOLEAN"}, "CON": {"type": "BOOLEAN"},
                                    "INT": {"type": "BOOLEAN"}, "WIS": {"type": "BOOLEAN"}, "CHA": {"type": "BOOLEAN"}
                                },
                                "required": ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
                            },
                            "skills": {
                                "type": "OBJECT",
                                "description": "Map all 18 standard 5e skills to their proficiency tier integer: 0=None, 1=Proficient, 2=Expertise"
                            },
                            "tools": {"type": "ARRAY", "items": {"type": "STRING"}},
                            "languages": {"type": "ARRAY", "items": {"type": "STRING"}},
                            "armor": {"type": "ARRAY", "items": {"type": "STRING"}},
                            "weapons": {"type": "ARRAY", "items": {"type": "STRING"}}
                        },
                        "required": ["saving_throws", "skills", "tools", "languages", "armor", "weapons"]
                    },
                    "features": {"type": "OBJECT", "description": "Key-value map of named character traits to their rules description text"},
                    "spell_slots": {
                        "type": "OBJECT",
                        "properties": {
                            "max_slots": {"type": "OBJECT", "description": "e.g., {'1st': 4, '2nd': 2}"}
                        }
                    },
                    "inventory": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "name": {"type": "STRING"},
                                "quantity": {"type": "INTEGER"},
                                "weight": {"type": "NUMBER"}
                            },
                            "required": ["name", "quantity", "weight"]
                        }
                    }
                },
                "required": ["character_name", "race", "class_and_level", "level", "base_max_hp", "base_ac", "speed", "stats", "proficiencies", "features", "inventory"]
            }

            print(f"Executing Gemini Smart Extraction for Hero ID {char_id}...")
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[json_dump_str, extraction_prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=gemini_response_schema
                )
            )

            # 3. Parse Gemini output string back into a structural Python dictionary framework
            clean_json = json.loads(response.text)

            # 4. Invoke your deterministic Game Engine to calculate final skill modifiers and initiative bonuses
            calculated_deltas = game_engine.process_level_up_delta({
                "stats": clean_json["stats"],
                "proficiencies": clean_json["proficiencies"],
                "level": clean_json["level"]
            })

            # 5. Check if a pre-existing character document delta exists inside MongoDB for this session
            # This protects current session health values from getting overwritten during re-imports!
            existing_sheet = await CharacterSheet.find_one(
                CharacterSheet.channel_id == channel_id,
                CharacterSheet.player_id == player_id
            )
            session_hp_cache = existing_sheet.vitals.session_current_hp if existing_sheet else None
            session_slots_cache = existing_sheet.spellcasting.used_slots if (existing_sheet and existing_sheet.spellcasting) else {}

            # 6. Rebuild and map the unified Beanie Document instance
            vitals = CharacterVitals(
                session_current_hp=session_hp_cache, # Preserves live session damage values!
                base_max_hp=clean_json["base_max_hp"],
                base_ac=clean_json["base_ac"],
                speed=clean_json["speed"],
                initiative_bonus=calculated_deltas["initiative_bonus"],
                active_conditions=existing_sheet.vitals.active_conditions if existing_sheet else []
            )

            proficiencies = CharacterProficiencies(
                saving_throws=clean_json["proficiencies"]["saving_throws"],
                skills=clean_json["proficiencies"]["skills"],
                tools=clean_json["proficiencies"]["tools"],
                languages=clean_json["proficiencies"]["languages"],
                armor=clean_json["proficiencies"]["armor"],
                weapons=clean_json["proficiencies"]["weapons"]
            )

            spell_slots = None
            if "spell_slots" in clean_json and clean_json["spell_slots"]:
                spell_slots = SpellSlots(
                    max_slots=clean_json["spell_slots"].get("max_slots", {}),
                    used_slots=session_slots_cache 
                )

            inventory_items = [
                InventoryItem(name=item["name"], quantity=item["quantity"], weight=item["weight"])
                for item in clean_json["inventory"]
            ]
    
            # Re-inject items picked up mid-game if they exist in the old sheet state
            if existing_sheet:
                for item in existing_sheet.inventory:
                    if item.is_loot_found_mid_session:
                        inventory_items.append(item)

            # Assemble the complete document contract
            synced_sheet = CharacterSheet(
                channel_id=channel_id,
                player_id=player_id,
                ddb_character_id=char_id,
                character_name=clean_json["character_name"],
                class_and_level=clean_json["class_and_level"],
                level=clean_json["level"],
                proficiency_bonus=calculated_deltas["proficiency_bonus"],
                vitals=vitals,stats=clean_json["stats"],
                base_skills=calculated_deltas["base_skills"],
                proficiencies=proficiencies,
                features=clean_json["features"],
                spellcasting=spell_slots,
                inventory=inventory_items
                )

            # 7. Write directly to MongoDB
            await synced_sheet.save()
            print(f"💎 Character '{synced_sheet.character_name}' synced flawlessly to MongoDB.")
            return synced_sheet
            
        except Exception as e:
            print(f"❌ CRITICAL SYNC FAILURE in ddb_parser pipeline: {e}")
            return None

# Instantiate global parser service
ddb_parser = DDBParserService()