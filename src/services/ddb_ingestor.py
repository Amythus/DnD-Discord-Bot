import json
import re
import httpx
from services.gemini_client import gemini_service
from services.template_service import TemplateService
from database.models.identity.character import Character
from database.schemas.character_dto import CharacterDTO
from database.models.identity.registry import PlayerRegistry 

class DDBIngestorService:
    @staticmethod
    async def import_character(dndb_url: str, discord_user_id: int) -> Character:
        """
        Fetches raw D&D Beyond data, parses it via Gemini using strict DTO constraints,
        and saves it to the permanent Player Registry.
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

        print(f"✅ Successfully fetched character data for ID: {character_id}")

        # 2. Instantiate the Template Engine and render the Jinja prompt
        template_engine = TemplateService()
        compiled_prompt = template_engine.render_prompt("ddb_ingestion_prompt.jinja", data=raw_ddb_data)
        
        # 3. Request the centralized client
        client = gemini_service.get_client() 
        
        print("🤖 Dispatching parsing request to Gemini API (Locked Structural Schema Mode)...")

        # 4. Generate structured output 
        parsed_dto = await gemini_service.generate_structured_output(
            model='gemini-3.1-flash-lite',
            contents=compiled_prompt,
            response_schema=CharacterDTO 
        )

        # Registry Handshake with character-player registry
        registry = await PlayerRegistry.find_one(
            PlayerRegistry.discord_user_id == discord_user_id,
            PlayerRegistry.dndb_character_id == str(character_id)
        )

        # Query if character exists within registry
        existing_char = None
        if registry and registry.active_character_id:
            existing_char = await Character.get(registry.active_character_id)


        # 6. Insert into MongoDB, check to see if character exists + upsert

        is_new = False

        insert_kwargs = {
            **parsed_dto.model_dump(),
            "discord_user_id": discord_user_id,
            "dndb_uri": dndb_url
        }
        new_character = Character(**insert_kwargs)    
        
        if existing_char:
            new_character.id = existing_char.id
            await new_character.replace()
        else:
            is_new = True
            await new_character.save()
            
        # 7. Update registry with the new character
        if not registry:
            # On creation, we can pass the document instance or ID
            registry = PlayerRegistry(
                discord_user_id=discord_user_id,
                active_character_id=new_character.id,
                dndb_uri=str(dndb_url),
                dndb_character_id=str(character_id)
            )
            await registry.save()
        else:
            # On update, explicitly set the ID
            registry.active_character_id = new_character.id
            await registry.save()

        return new_character, is_new