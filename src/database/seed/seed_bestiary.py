import asyncio
import json
import sys
from pathlib import Path
from pymongo import UpdateOne

# Central application hooks
from database.connection import init_database
from database.models import Monster

""" Command to run seeding script
docker exec -it dnd_discord_bot python -m database.seed.seed_bestiary
"""

async def seed_monsters():
    # 1. Initialize Beanie via the centralized connection model
    db_success = await init_database()
    if not db_success:
        print("Aborting seed operation: Database connection failed.")
        sys.exit(1)
        
    # 2. Dynamically locate the directory where this script lives
    script_dir = Path(__file__).parent
    
    # Use glob to discover all files matching 'bestiary-*.json'
    target_pattern = "./bestiary/bestiary-*.json"
    json_files = list(script_dir.glob(target_pattern))
    
    if not json_files:
        print(f"Error: No bestiary datasets found matching pattern '{target_pattern}' in {script_dir}")
        return

    print(f"Discovered {len(json_files)} target datasets for processing:")
    for file_path in json_files:
        print(f" - {file_path.name}")

    bulk_operations = []
    total_raw_processed = 0
    
    # 3. Iterate over every discovered bestiary payload file
    for json_path in json_files:
        print(f"\nProcessing source dataset: {json_path.name}")
        
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"CRITICAL: Failed to parse JSON body for {json_path.name}. Skipping file. Error: {e}")
            continue
            
        monster_list = data.get("monster", [])
        if not monster_list:
            print(f" -> Array Context Notice: Missing or empty 'monster' block in {json_path.name}. Skipping.")
            continue

        print(f" -> Compiling batch ops for {len(monster_list)} records from {json_path.name}...")
        total_raw_processed += len(monster_list)
        
        for raw_monster in monster_list:
            # Handle 5e.tools reference copies/skeletons if they pop up
            if "_copy" in raw_monster:
                continue
                
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
                print(f"   [Skipping Profile] '{raw_monster.get('name', 'Unknown')}' inside {json_path.name}: {ve}")
                continue

    # 4. Execute the combined payload transaction across all files
    if bulk_operations:
        print(f"\nExecuting grand payload synchronization for {len(bulk_operations)} combined documents...")
        collection = Monster.get_motor_collection()
        result = await collection.bulk_write(bulk_operations, ordered=False)
        
        upserted_modified = result.upserted_count + result.modified_count
        print(f"\n========================================================")
        print(f"Seed synchronization complete across all datasets!")
        print(f"Total raw profiles encountered: {total_raw_processed}")
        print(f"Successfully Upserted/Modified fields: {upserted_modified}")
        print(f"========================================================")
    else:
        print("\nData processing phase yielded 0 valid document payloads. Halting.")

if __name__ == "__main__":
    asyncio.run(seed_monsters())