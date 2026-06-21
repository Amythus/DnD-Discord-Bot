import os
import asyncio
from pathlib import Path
from pymongo import UpdateOne
from google import genai
from google.genai import types

from config.settings import AppSettings  # Case-insensitive safe environment loader
from database.connection import init_db  # Beanie async MongoDB initializer
from database.models.static.node import Node  # Original Beanie Document model
from database.seed.adventure_dto import AdventureMatrixResponse 

async def ingest_adventure(file_name: str = "adventure.md"):
    # 1. Initialize Configuration and Clients
    settings = AppSettings()
    api_key = getattr(settings, "gemini_api_key", os.getenv("GEMINI_API_KEY"))
    
    if not api_key:
        print("❌ Error: GEMINI_API_KEY could not be located in environment settings.")
        return

    client = genai.Client(api_key=api_key)
    
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
    compiled_prompt = template_engine.render(
        "adventure_prompt.jinja", 
        adventure_text=adventure_text
    )

    print("🤖 Dispatching parsing request to Gemini API (Locked Structural Schema Mode)...")
    
    try:
        response = client.models.generate_content(
            model='gemini-3.5', 
            contents=f"Analyze and parse the following adventure text into a flat structural node matrix:\n\n{adventure_text}",
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.1,  # Low temperature forces deterministic data extraction
                response_mime_type="application/json",
                response_schema=AdventureMatrixResponse,
            ),
        )
    except Exception as e:
        print(f"❌ Gemini Engine Ingestion Failure: {e}")
        return

    # 4. Parse Structured Output Text Back into DTO Instance
    try:
        parsed_matrix = AdventureMatrixResponse.model_validate_json(response.text)
        print(f"✅ Successfully extracted adventure schema: '{parsed_matrix.adventure_id}'")
        print(f"📊 Identified {len(parsed_matrix.nodes)} topological map locations inside text.")
    except Exception as e:
        print(f"❌ Structural Validation Crash: Returned response structure drifted from target DTO limits. Error: {e}")
        return

    # 5. Initialize Database Sockets via Beanie Connection Core
    print("🔌 Opening async connection channel to MongoDB instance...")
    await init_db()

    # 6. Transform Pure DTO Objects into Beanie Database Operations
    bulk_operations = []
    
    for index, node_dto in enumerate(parsed_matrix.nodes):
        # Convert DTO dictionary properties directly into your structural Beanie record
        node_data = node_dto.model_dump()
        node_data["adventure_id"] = parsed_matrix.adventure_id
        
        # If this is the CAMPAIGN_ROOT initialization node, seed the full quest ledger
        if node_dto.node_type == "CAMPAIGN_ROOT" and index == 0:
            node_data["quest_registry"] = [q.model_dump() for q in parsed_matrix.quest_registry]
        else:
            node_data["quest_registry"] = []

        # Instantiating the Beanie layout enforces Pydantic V2 validations prior to transit
        validated_beanie_node = Node(**node_data)
        
        # Compile unique composite replacement query rules: {"adventure_id": ..., "node_id": ...}
        filter_criteria = {
            "adventure_id": validated_beanie_node.adventure_id,
            "node_id": validated_beanie_node.node_id
        }
        
        operation = UpdateOne(
            filter_criteria,
            {"$set": validated_beanie_node.model_dump(exclude={"id"})},
            upsert=True
        )
        bulk_operations.append(operation)

    # 7. Execute Idempotent Mass Bulk Writing
    if bulk_operations:
        print(f"🗄️ Executing bulk upsert transaction across {len(bulk_operations)} database documents...")
        collection = Node.get_motor_collection()
        result = await collection.bulk_write(bulk_operations)
        print(f"🎉 Ingestion Complete! Matched: {result.matched_count}, Upserted IDs: {result.upserted_count}")
    else:
        print("⚠️ Warning: Operations array empty. No structural data points recorded.")

if __name__ == "__main__":
    # Allows localized execution from terminal inside your Docker runtime environment
    asyncio.run(ingest_adventure())