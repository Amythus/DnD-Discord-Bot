import asyncio
import json
import sys
from pathlib import Path
from pymongo import UpdateOne

# Central application hooks
from database.connect import init_database
from database.models import Monster

""" Command to run seeding script
docker run --rm -it \
  --network dnd_shared_network \
  -e MONGO_URI="mongodb://your_mongo_container_name:27017/dnd_bot_db" \
  your_bot_image_name python -m src.database.seed.seed_monsters
"""

""" Command to run seeding script
docker run --rm -it \
  --network dnd_shared_network \
  -e MONGO_URI="mongodb://mongodb-dnd:27017/dnd_bot_db" \
  dnd_discord_bot python -m src.database.seed.seed_monsters
"""


async def seed_monsters():
    # 1. Initialize Beanie via the centralized connection model
    db_success = await init_database()
    if not db_success:
        print("Aborting seed operation: Database connection failed.")
        sys.exit(1)
        
    # 2. Dynamically look up the JSON path relative to this script's directory
    script_dir = Path(__file__).parent
    json_path = script_dir / "bestiary-mm.json"
    
    print(f"Locating dataset at structural path: {json_path}")
    if not json_path.exists():
        print(f"Error: Missing targeted 5e.tools bestiary at {json_path}")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    monster_list = data.get("monster", [])
    if not monster_list:
        print("Empty payload or missing root 'monster' array context.")
        return

    print(f"Compiling batch ops for {len(monster_list)} records...")
    bulk_operations = []
    
    for raw_monster in monster_list:
        try:
            validated_monster = Monster(**raw_monster)
            monster_dict = validated_monster.model_dump(by_alias=True, exclude={"id"})
            
            op = UpdateOne(
                {"name": validated_monster.name},
                {"$set": monster_dict},
                upsert=True
            )
            bulk_operations.append(op)
        except Exception as ve:
            print(f"Skipping profile for '{raw_monster.get('name', 'Unknown')}' due to verification gap: {ve}")
            continue

    if bulk_operations:
        print(f"Executing payload synchronization for {len(bulk_operations)} documents...")
        collection = Monster.get_motor_collection()
        result = await collection.bulk_write(bulk_operations, ordered=False)
        print(f"Seed synchronization complete. Upserted/Modified fields: {result.upserted_count + result.modified_count}")
    else:
        print("Data processing phase yields 0 valid document payloads. Halting.")

if __name__ == "__main__":
    asyncio.run(seed_monsters())