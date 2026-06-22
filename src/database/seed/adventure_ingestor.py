import os
import json
from typing import List, Dict, Any
from pydantic import BaseModel, Field
import asyncio
from pathlib import Path
from pymongo import UpdateOne

from google.genai import types

from database.connection import init_database  # Beanie async MongoDB initializer
from database.models.spatial.node import GameNode  # Original Beanie Document model
from database.models.campaign.adventure_blueprint import AdventureRootBlueprint
from database.schemas.node_dto import NodeDTO  # Pydantic DTO for
from database.schemas.adventure_dto import AdventureDTO

from services.gemini_client import gemini_service
from services.template_service import TemplateService

""" Command to run seeding script
docker exec -it dnd_discord_bot python -m database.seed.adventure_ingestor
"""

async def ingest_adventure(file_name: str = "adventure.md"):
    """
    Orchestrates the 3-Pass Adventure Ingestion Pipeline.
    Pass 1 consumes the entire markdown asset via Gemini.
    Pass 2 iterates through the array one node at a time to validate graph integrity.
    Pass 3 compiles the final master campaign blueprint template.
    """    

    await init_database()

    # ===================================================
    # PASS 1: Sequential Registration
    # ===================================================

    # 1. Initialize Clients via Shared Service
    client = gemini_service.get_client()
    # 2. Establish Relative Path Discovery
    script_dir = Path(__file__).parent
    target_md_path = script_dir / "adventures" / file_name
    
    if not target_md_path.exists():
        print(f"❌ Error: Targeted markdown source file missing at: {target_md_path}")
        return

    print(f"📖 Reading adventure data from: {target_md_path.name}...")
    adventure_text = target_md_path.read_text(encoding="utf-8")

    # 3. Compile System Prompt Instructions
    # Pass text to Jinja to compile the specialized input prompt
    template_engine = TemplateService()
    compiled_prompt = template_engine.render_prompt("adventure_ingestion_prompt.jinja", adventure_text=adventure_text)

    print("🤖 Dispatching parsing request to Gemini API (Locked Structural Schema Mode)...")

    generation_response = await gemini_service.generate_structured_output(
            model='gemini-3.1-flash-lite',
            contents=compiled_prompt,
            response_schema=AdventureDTO
        )

    adventure_id = generation_response.adventure_id
    node_dto_array: List[NodeDTO] = generation_response.nodes

    print(f"✅ Pass 1 Complete: Extracted {len(node_dto_array)} flat Node DTOs.")

    print("🔗 Commencing iteration and inserting nodes into the database...")
    
    processed_node_ids = set()
    
    for idx, node_dto in enumerate(node_dto_array):
        print(f"   ↳ Ingesting node [{idx + 1}/{len(node_dto_array)}]: {node_dto.node_id}")
        
        try:
            # 1. Enforce validation guarantees by unpacking the verified DTO attributes
            node_data = node_dto.model_dump()
            
            # 2. Check for unique key continuity to enforce map idempotency
            existing_node = await GameNode.find_one({
                "adventure_id": adventure_id,
                "node_id": node_dto.node_id
            })
            
            if existing_node:
                # Sync updates onto the tracking record if it already exists
                live_node = GameNode(**node_data)
                live_node.id = existing_node.id
                await live_node.replace()
            else:
                # Commit a clean flat graph segment to your MongoDB cluster
                live_node = GameNode(**node_data)
                await live_node.save()
                
            processed_node_ids.add(node_dto.node_id)
            
        except Exception as e:
            # Catch localized validation or DB schema errors without failing the complete chain
            print(f"❌ Structural Failure on Node ID '{node_dto.node_id}': {str(e)}")
            continue

    # ===================================================
    # PASS 2: VALIDATION & LINKING (One node at a time)
    # ===================================================

    print("\n🛡️ Running Pass 2: Topological check across navigation exit thresholds...")
    broken_links_detected = 0
    starting_node_id = None

    for node_dto in node_dto_array:
        # Only validate nodes that successfully passed database serialization in Pass 1
        if node_dto.node_id not in processed_node_ids:
            continue
            
        # Track the starting node for Pass 3 compilation rules (e.g. your CAMPAIGN_ROOT)
        if node_dto.node_type == "CAMPAIGN_ROOT":
            starting_node_id = node_dto.node_id

        # 1. Validate Parent Adjacency Pointer
        if node_dto.parent_node_id and node_dto.parent_node_id not in processed_node_ids:
            print(f"  ⚠️ Link Warning: Node '{node_dto.node_id}' references an orphaned parent_node_id: '{node_dto.parent_node_id}'")
            broken_links_detected += 1

        # 2. Validate Navigation Exit Grid Targets
        # Assumes node_dto.navigation contains a list or dictionary of exits/links
        # Adjust the attribute extraction below to match your precise NavigationGrid Pydantic structure
        if hasattr(node_dto, "navigation") and node_dto.navigation:
            # Assuming your model has a structured array of exit objects: e.g., node_dto.navigation.exits
            exits = getattr(node_dto.navigation, "exits", [])
            for game_exit in exits:
                target = getattr(game_exit, "target_node_id", None)
                if target and target not in processed_node_ids:
                    print(f"  ❌ Graph Break: Node '{node_dto.node_id}' points to a non-existent exit target: '{target}'")
                    broken_links_detected += 1

    print(f"✅ Pass 2 Complete. Validated structural integrity. Broken references found: {broken_links_detected}")
    
    # ===================================================
    # PASS 3: MAP COMPILATION (Blueprint Assembly)
    # ===================================================

    print("\n🏗️ Commencing Pass 3: Compiling master campaign blueprint template...")
    
    # Ensure a legitimate starting node exists from Pass 2 data checking
    if not starting_node_id:
        starting_node_id = list(processed_node_ids)[0] if processed_node_ids else "start_node"
        print(f"⚠️ Warning: No CAMPAIGN_ROOT type detected. Defaulting entry room to: {starting_node_id}")

    try:
        # Check if a blueprint for this module already exists to keep lookups idempotent
        existing_blueprint = await AdventureRootBlueprint.find_one({
            "adventure_id": adventure_id
        })
        
        # Hydrate the master blueprint directly using parameters captured from generation_response
        blueprint_data = {
            "adventure_id": adventure_id,
            "module_name": generation_response.module_name,
            "starting_node_id": starting_node_id,
            "initiator_prompt": generation_response.initiator_prompt,
            "default_npc_dispositions": generation_response.default_npc_dispositions,
            "initial_story_flags": generation_response.initial_story_flags,
            "master_quest_registry": generation_response.master_quest_registry
        }
        
        if existing_blueprint:
            print(f"🔄 Syncing blueprint updates onto existing token tracking record...")
            live_blueprint = AdventureRootBlueprint(**blueprint_data)
            live_blueprint.id = existing_blueprint.id
            await live_blueprint.replace()
        else:
            print(f"💾 Saving new atomic campaign master template blueprint to database...")
            live_blueprint = AdventureRootBlueprint(**blueprint_data)
            await live_blueprint.save()
            
        print(f"🚀 Master Campaign Ready: '{generation_response.module_name}' is fully validated.")
        
    except Exception as e:
        print(f"❌ Critical Failure Compiling Pass 3 Campaign Template: {str(e)}")
        return {"status": "FAILED_BLUEPRINT_COMPILATION", "error": str(e)}

    return {
        "adventure_id": adventure_id,
        "status": "SUCCESS",
        "nodes_ingested_count": len(processed_node_ids),
        "starting_node_id": starting_node_id
    }

async def main():
    # FIXED: Establish asynchronous database loop initialization before routing records
    print("🔌 Initializing connection to MongoDB Cluster...")
    # await init_database()
    await ingest_adventure()

if __name__ == "__main__":
    asyncio.run(ingest_adventure())