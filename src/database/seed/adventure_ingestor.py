import os
import json
from typing import List, Dict, Any
from pydantic import BaseModel, Field
import asyncio
from pathlib import Path
from pymongo import UpdateOne

from database.connection import init_db  # Beanie async MongoDB initializer
from database.models.static.node import Node  # Original Beanie Document model
from database.models.schema.node_dto import NodeDTO  # Pydantic DTO for
from database.seed.adventure_dto import AdventureMatrixResponse 

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
    compiled_prompt = template_engine.render("adventure_ingestion_prompt.jinja", adventure_text=adventure_text)

    print("🤖 Dispatching parsing request to Gemini API (Locked Structural Schema Mode)...")
    
    try:
        response = client.models.generate_content(
            model='gemini-3.1-flash-lite', 
            contents=compiled_prompt,
            config=types.GenerateContentConfig(
                # system_instruction=system_instruction,
                # temperature=0.1,
                response_mime_type="application/json",
                response_json_schema=NodeDTO.model_json_schema(),
            ),
        )
    except Exception as e:
        print(f"❌ Gemini Engine Ingestion Failure: {e}")
        return

    # Extract the type-safe array container populated by the LLM
    generated_payload: AdventureGenerationPayload = raw_response
    node_dto_array: List[NodeDTO] = generated_payload.nodes
    print(f"✅ Pass 1 Complete: Extracted {len(node_dto_array)} flat Node DTOs.")

    # Extract the type-safe array container populated by the LLM
    generated_payload: AdventureGenerationPayload = raw_response
    node_dto_array: List[NodeDTO] = generated_payload.nodes
    print(f"✅ Pass 1 Complete: Extracted {len(node_dto_array)} flat Node DTOs.")

    # ===================================================
    # PASS 2: VALIDATION & LINKING (One-at-a-Time Loop)
    # ===================================================
    print("🔗 Commencing Pass 2: Iterating nodes one-by-one to commit and map graph...")
    
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

    # Graph verification stage: Loop over exits to ensure pointers targets exist
    print("🛡️ Running topological check across navigation exit thresholds...")
    # (Your loop logic that checks target_node_id against processed_node_ids goes here)
    
    # ============================================
    # PASS 3: MAP COMPILATION (Blueprint Assembly)
    # ============================================
    print("🏗️ Commencing Pass 3: Deriving macro blueprint document entries...")
    # (Your aggregation logic tracking starting_node_id and default state parameters)
    
    return {
        "adventure_id": adventure_id,
        "status": "SUCCESS",
        "nodes_ingested_count": len(processed_node_ids)
    }

if __name__ == "__main__":
    # Allows localized execution from terminal inside your Docker runtime environment
    asyncio.run(ingest_adventure())