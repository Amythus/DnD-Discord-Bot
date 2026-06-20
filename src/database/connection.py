import sys
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

# Modern architecture hook: Pull your clean centralized model registry 
from database.models import __all_models__
from config.settings import settings

async def init_database(mongo_uri: Optional[str] = None) -> bool:
    """
    Establishes an asynchronous connection pool to the MongoDB server
    and binds all centralized registry data schemas into Beanie document collections.
    """
    target_uri = str(mongo_uri if mongo_uri is not None else settings.mongo_uri)
    
    try:
        print("🔌 Launching asynchronous Motor connection pool to MongoDB...")
        client = AsyncIOMotorClient(target_uri)
        
        # Extracts default DB name out of connection string (e.g. mongodb://.../dnd_bot_db)
        db_handle = client.get_default_database()
        
        print(f"🗃️ Target database resolved: '{db_handle.name}'. Initializing Beanie document mappings...")
        
        # Initialize Beanie dynamically using our centralized array pass
        await init_beanie(
            database=db_handle,
            # document_models=__all_models__
            document_models=__all_models__
        )
        
        print("🚀 Beanie ODM mappings established. Local collection schemas matched successfully.")
        return True

    except ConnectionError as e:
        print(f"❌ DATABASE CONNECTION FAILURE: Unable to locate or authenticate with MongoDB node: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"❌ CRITICAL INFRASTRUCTURE CRASH during Beanie initialization pipeline: {e}", file=sys.stderr)
        return False