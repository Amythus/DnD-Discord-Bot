import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, Any
from pymongo import UpdateOne

# Central application hooks
from database.connection import init_database
from database.models.static.item import Item

""" Command to run seeding script
docker exec -it dnd_discord_bot python -m database.seed.seed_items
"""

async def seed_items():
    # 1. Initialize Beanie via the centralized connection model
    db_success = await init_database()
    if not db_success:
        print("Aborting seed operation: Database connection failed.")
        sys.exit(1)
        
    # 2. Locate the static items directory
    script_dir = Path(__file__).parent
    items_dir = script_dir / "items"
    
    base_file_path = items_dir / "items-base.json"
    magic_file_path = items_dir / "items.json"
    
    # Sanity check file presence
    if not base_file_path.exists() or not magic_file_path.exists():
        print(f"CRITICAL: Missing item datasets in {items_dir}. Ensure both 'items-base.json' and 'items.json' are pulled.")
        return

    bulk_operations = []
    total_raw_processed = 0
    
    # This dictionary will act as our local hydration cache: {"longsword|phb": {raw_dict_data}}
    base_items_cache: Dict[str, dict] = {}

    # ==========================================
    # PASS 1: PARSE & CACHE MUNDANE BASE ITEMS
    # ==========================================
    print(f"\n[PASS 1] Processing foundational dataset: {base_file_path.name}")
    try:
        with open(base_file_path, "r", encoding="utf-8") as f:
            base_data = json.load(f)
    except Exception as e:
        print(f"CRITICAL: Failed to parse JSON body for {base_file_path.name}. Aborting seeding pipeline. Error: {e}")
        return

    # 5e.tools structure can use "baseitem" or "item" as its root key array
    base_item_list = base_data.get("baseitem", []) or base_data.get("item", [])
    print(f" -> Found {len(base_item_list)} baseline template elements.")
    
    for raw_base in base_item_list:
        if "_copy" in raw_base:
            continue
            
        name = raw_base.get("name")
        source = raw_base.get("source", "PHB").lower()
        
        if not name:
            continue
            
        # 5e.tools references base items using a lowercase pipe syntax: "name|source"
        cache_key = f"{name.lower()}|{source}"
        
        try:
            # Enforce is_magic is explicitly False for foundational records
            raw_base["is_magic"] = False
            
            validated_base = Item(**raw_base)
            base_dict = validated_base.model_dump(by_alias=True, exclude={"id"})
            
            # Populate our optimization dictionary for Pass 2 hydration
            base_items_cache[cache_key] = base_dict
            
            # Queue the upsert operation
            op = UpdateOne(
                {"name": validated_base.name, "source": validated_base.source},
                {"$set": base_dict},
                upsert=True
            )
            bulk_operations.append(op)
            total_raw_processed += 1
            
        except Exception as ve:
            print(f"   [Skipping Template Profile] '{name}' inside {base_file_path.name}: {ve}")
            continue

    print(f" -> Pass 1 Complete. Cached {len(base_items_cache)} baseline templates in runtime memory.")

    # ==========================================
    # PASS 2: PARSE, HYDRATE & MERGE MAGIC ITEMS
    # ==========================================
    print(f"\n[PASS 2] Processing magical artifact dataset: {magic_file_path.name}")
    try:
        with open(magic_file_path, "r", encoding="utf-8") as f:
            magic_data = json.load(f)
    except Exception as e:
        print(f"CRITICAL: Failed to parse JSON body for {magic_file_path.name}. Aborting seeding pipeline. Error: {e}")
        return

    magic_item_list = magic_data.get("item", [])
    print(f" -> Found {len(magic_item_list)} variant/magical elements.")

    for raw_magic in magic_item_list:
        if "_copy" in raw_magic:
            continue
            
        name = raw_magic.get("name", "Unknown")
        
        try:
            # Check if this item inherits properties from a template item (e.g., "longsword|phb")
            base_item_ref = raw_magic.get("baseitem")
            hydrated_payload = {}

            if base_item_ref:
                # Normalize reference string for precise lookup
                lookup_key = base_item_ref.lower()
                cached_properties = base_items_cache.get(lookup_key)
                
                if cached_properties:
                    # Strip database or system keys if present, but carry over properties, values, and weight
                    keys_to_ignore = {"id", "_id", "name", "source", "page", "entries"}
                    hydrated_payload = {k: v for k, v in cached_properties.items() if k not in keys_to_ignore}
                else:
                    print(f"   [Inheritance Warning] '{name}' references template reference '{base_item_ref}', but it wasn't found in memory cache.")

            # Construct the final merged object layout, prioritizing raw_magic explicit values over base templates
            merged_item_data = {**hydrated_payload, **raw_magic}
            merged_item_data["is_magic"] = True  # Explicitly brand Pass 2 as magic modifiers

            # Run through strict Pydantic parsing
            validated_magic = Item(**merged_item_data)
            magic_dict = validated_magic.model_dump(by_alias=True, exclude={"id"})

            op = UpdateOne(
                {"name": validated_magic.name, "source": validated_magic.source},
                {"$set": magic_dict},
                upsert=True
            )
            bulk_operations.append(op)
            total_raw_processed += 1

        except Exception as ve:
            print(f"   [Skipping Magical Profile] '{name}' inside {magic_file_path.name}: {ve}")
            continue

    # ==========================================
    # GLOBAL PAYLOAD EXECUTION HANDSHAKE
    # ==========================================
    if bulk_operations:
        print(f"\nExecuting grand payload synchronization for {len(bulk_operations)} combined items...")
        collection = Item.get_motor_collection()
        result = await collection.bulk_write(bulk_operations, ordered=False)
        
        upserted_modified = result.upserted_count + result.modified_count
        print(f"\n========================================================")
        print(f"Item seed synchronization complete across all passes!")
        print(f"Total raw source item blocks encountered: {total_raw_processed}")
        print(f"Successfully Upserted/Modified fields inside collection: {upserted_modified}")
        print(f"========================================================")
    else:
        print("\nData processing pipeline yielded 0 valid unified document payloads. Halting.")

if __name__ == "__main__":
    asyncio.run(seed_items())