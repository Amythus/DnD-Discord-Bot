import json
import re
import httpx
from services.gemini_client import gemini_service
from services.template_service import TemplateService
from database.models.identity.character import Character
from database.schemas.character_dto import DDBParsedCharacter

class DDBIngestorService:
    @staticmethod
    async def import_character(dndb_url: str, discord_user_id: int) -> Character:
        """
        Fetches raw D&D Beyond data, parses it via Gemini using strict DTO constraints,
        and saves it to the permanent Global Tracker.
        """
        # 1. Safely extract the ID from the D&D Beyond Link
        match = re.search(r'characters/(\d+)', dndb_url)
        if not match:
            raise ValueError("Invalid D&D Beyond URL or Character ID.")
        character_id = int(match.group(1))

        print("🤖 Fetching Character JSON from DDB Endpoint")

        api_endpoint = f"https://character-service.dndbeyond.com/character/v5/character/{character_id}"
        async with httpx.AsyncClient() as client:
            response = await client.get(api_endpoint)
            if response.status_code != 200:
                raise ValueError(f"Failed to fetch sheet data. Status: {response.status_code}")
            raw_ddb_data = response.json()

        print("✅ Successfully fetched character data for ID: {character_id}")

        # 2. Instantiate the Template Engine and render the Jinja prompt
        template_engine = TemplateService()
        prompt_text = template_engine.render_prompt("ddb_ingestion_prompt.jinja", data=raw_ddb_data)
        
        # 3. Request the centralized client
        client = gemini_service.get_client() 
        
        print("🤖 Dispatching parsing request to Gemini API (Locked Structural Schema Mode)...")

        # 4. Generate structured output
        # Remove 'await' here
        response = client.models.generate_content(
            model='gemini-3.1-flash-lite',
            contents=prompt_text,
            config={
                "response_mime_type": "application/json",
            }
        )

        print("✅ Successfully parsed character data into structured JSON.")
        
        # 5. Load the validated JSON
        # parsed_json = json.loads(response.text)
        parsed_dto = DDBParsedCharacter.model_validate_json(response.text)
        
        # 6. Database Handshake: Map the pure DTO into your actual Beanie Model
        # Ensure we attach the Discord Owner ID to prevent state drift
        insert_kwargs = {
            **parsed_dto.model_dump(),
            "discord_user_id": discord_user_id,
            "dndb_uri": dndb_url
        }
        
        # Handle field alias fallback between dndb_character_id vs dnd_beyond_character_id
        target_field = "dndb_character_id" if hasattr(Character, "dndb_character_id") else "dnd_beyond_character_id"
        
        # Assuming you extract the character_id from the URL earlier in the process
        insert_kwargs[target_field] = character_id 
        
        existing_char = await Character.find_one({target_field: insert_kwargs.get(target_field)})
        
        new_character = Character(**insert_kwargs)
        if existing_char:
            new_character.id = existing_char.id
            await new_character.replace()
        else:
            await new_character.save()
            
        return new_character