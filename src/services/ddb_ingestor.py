import json
from database.schemas.character_dto import DDBParsedCharacter
from services.gemini_client import gemini_service
from services.template_service import TemplateService
from database.models.identity.character import Character
from database.schemas.adventure_dto import AdventureMatrixResponse

class DDBParserService:
    @staticmethod
    async def import_character(dndb_url: str, discord_user_id: int) -> Character:
        """
        Fetches raw D&D Beyond data, parses it via Gemini using strict DTO constraints,
        and saves it to the permanent Global Tracker.
        """
        # 1. Fetch raw data from D&D Beyond (Implementation omitted for brevity)
        # raw_ddb_data = await fetch_ddb_api(dndb_url)
        raw_ddb_data = {} # Placeholder for your fetch logic
        
        # 2. Instantiate the Template Engine and render the Jinja prompt
        template_engine = TemplateService()
        prompt_text = template_engine.render("char_schema.jinja", data=raw_ddb_data)
        
        # 3. Request the centralized client
        client = gemini_service.get_client() 
        
        # 4. Generate structured output using the strictly locked DTO
        response = await client.models.generate_content(
            model='gemini-3.1-flash-lite',
            contents=prompt_text,
            config={
                "response_mime_type": "application/json",
                "response_schema": DDBParsedCharacter,
            }
        )
        
        # 5. Load the validated JSON
        parsed_json = json.loads(response.text)
        
        # 6. Database Handshake: Map the pure DTO into your actual Beanie Model
        # Ensure we attach the Discord Owner ID to prevent state drift
        insert_kwargs = {
            **parsed_json,
            "discord_user_id": discord_user_id,
            "dndb_uri": dndb_url
        }
        
        # Handle field alias fallback between dndb_character_id vs dnd_beyond_character_id
        target_field = "dndb_character_id" if hasattr(Character, "dndb_character_id") else "dnd_beyond_character_id"
        
        # Assuming you extract the character_id from the URL earlier in the process
        # insert_kwargs[target_field] = character_id 
        
        existing_char = await Character.find_one({target_field: insert_kwargs.get(target_field)})
        
        new_character = Character(**insert_kwargs)
        if existing_char:
            new_character.id = existing_char.id
            await new_character.replace()
        else:
            await new_character.save()
            
        return new_character