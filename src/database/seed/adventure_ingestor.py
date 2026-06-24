import os
import json
import asyncio
from pathlib import Path
from typing import List, Set, Tuple, Optional, Dict, Any

from database.connection import init_database  
from database.models.spatial.node import GameNode  
from database.models.campaign.adventure_blueprint import AdventureBlueprint
from database.schemas.node_dto import NodeDTO  
from database.schemas.mapping_dto import AdventureMapDTO, NodeDiscoveryItem

from services.gemini_client import gemini_service
from services.template_service import TemplateService

""" Command to run seeding script
docker exec -it dnd_discord_bot python -m database.seed.adventure_ingestor
"""

# =====================================================================
# PIPELINE PHASE HELPERS
# =====================================================================

async def _execute_map_discovery(raw_text: str) -> AdventureMapDTO:
    """
    PHASE 1: Map Pass.
    Discovers the structural campaign layout and returns an intermediate DTO.
    """
    print("🤖 [Phase 1] Dispatching Map Discovery to Gemini API...")
    
    template_engine = TemplateService()
    compiled_prompt = template_engine.render_prompt(
        "adventure_mapping_prompt.jinja", \
        adventure_text=raw_text
    )

    map_metadata: AdventureMapDTO = await gemini_service.generate_structured_output(
        model='gemini-3.1-flash-lite',
        contents=compiled_prompt,
        response_schema=AdventureMapDTO
    )
    
    print(f"✅ [Phase 1] Map discovered successfully. Registered {len(map_metadata.node_registry)} distinct areas.")
    return map_metadata


async def _execute_reduce_hydration_sequential(map_metadata: AdventureMapDTO) -> List[NodeDTO]:
    """
    PHASE 2: Reduce Pass (Hydration Loops).
    Iterates sequentially over discovered node segments with strict rate-limit protection.
    """
    print(f"⚡ [Phase 2] Launching sequential hydration loops over {len(map_metadata.discovered_nodes)} items...")
    template_engine = TemplateService()
    hydrated_nodes: List[NodeDTO] = []

    for idx, item in enumerate(map_metadata.discovered_nodes, start=1):
        print(f"⏳ [{idx}/{len(map_metadata.discovered_nodes)}] Extracting properties for local area: {item.title} ({item.node_id})")
        
        # FIXED: Explicitly inject node_registry to satisfy template cross-referencing constraints
        compiled_prompt = template_engine.render_prompt(
            "node_hydration_prompt.jinja",
            adventure_id=map_metadata.adventure_id,
            node_id=item.node_id,
            title=item.title,
            raw_text_segment=item.raw_text_segment,
            node_registry=map_metadata.node_registry
        )

        try:
            node_dto: NodeDTO = await gemini_service.generate_structured_output(
                model='gemini-3.1-flash-lite',
                contents=compiled_prompt,
                response_schema=NodeDTO
            )
            hydrated_nodes.append(node_dto)
            print(f"   ↳ Cleanly extracted {item.node_id} properties.")
            
        except Exception as ex:
            print(f"❌ [Phase 2 Error] Failed to process localized block {item.node_id} due to validation collapse: {ex}")
            # Fault Isolation: Log localized data payload errors but preserve the rest of the campaign execution flow
            continue

        # CRITICAL CONFIGURATION CHANGE: Throttled pacing block set to exactly 5 seconds to bypass API token quotas
        if idx < len(map_metadata.discovered_nodes):
            print("   💤 Enforcing api burst quota sleep boundary for 5 seconds...")
            await asyncio.sleep(5.0)

    return hydrated_nodes


async def _validate_and_repair_topology(adventure_id: str, node_array: List[NodeDTO]) -> Tuple[Optional[str], int]:
    """
    PHASE 3: Node Validation & Upsert Execution.
    Validates graph topologies, sets structural fallbacks, and updates documents idempotently.
    """
    print("🛡️ [Phase 3] Running graph integrity sweeps and committing layout changes to database...")
    if not node_array:
        return None, 0

    valid_ids: Set[str] = {node.node_id for node in node_array}
    starting_node_id: Optional[str] = None
    repaired_links = 0

    for node in node_array:
        # Detect the campaign entry anchor point
        # Fix: Safely handle if node_type is an Enum or a string
        node_type_val = getattr(node.node_type, 'value', node.node_type)
        if node_type_val == "CAMPAIGN_ROOT":
            starting_node_id = node.node_id

        # Validate that exits point to a real discovered room
        valid_exits = []
        for egress in node.navigation.exits:
            if egress.target_node_id in valid_ids:
                valid_exits.append(egress)
            else:
                print(f"   ⚠️ Broken Link: Exit matching target path '{egress.target_node_id}' points to a ghost segment. Purging exit.")
                repaired_links += 1
        node.navigation.exits = valid_exits


        # Idempotent DB execution layout protecting index constraints from document index duplicate crashes
        existing_doc = await GameNode.find_one(
            GameNode.adventure_id == adventure_id, 
            GameNode.node_id == node.node_id
        )
        
        if existing_doc:
            # Mirror updated fields into pre-existing document space
            update_data = node.model_dump(exclude={"id"})
            await existing_doc.update({"$set": update_data})
        else:
            # Create a brand new record on disk safely
            db_node = GameNode(**node.model_dump())
            await db_node.insert()

    return starting_node_id, repaired_links


async def _compile_master_blueprint(map_metadata: AdventureMapDTO, starting_node_id: str) -> bool:
    """
    PHASE 4: Blueprint Compilation.
    Saves immutable campaign configuration meta documents to MongoDB layer collections.
    """
    print(f"🗃️ [Phase 4] Compiling and consolidating blueprint specifications into production collections...")
    try:
        # Cast intermediate DTO arrays explicitly into the schema layouts expected by AdventureBlueprint
        hardened_triggers = []
        for trigger in map_metadata.global_behavior_triggers:
            hardened_triggers.append({
                "global_trigger_id": trigger.global_trigger_id,
                "conditions": trigger.conditions,
                "execution_effects": [
                    {
                        "effect_target": effect.effect_target,
                        "set_value": effect.set_value
                    } for effect in trigger.execution_effects
                ]
            })

        blueprint_data = {
            "adventure_id": map_metadata.adventure_id,
            "module_name": map_metadata.module_name,
            "starting_node_id": starting_node_id,
            "initiator_prompt": map_metadata.initiator_prompt,
            "story_hook": map_metadata.story_hook,
            "default_npc_dispositions": map_metadata.default_npc_dispositions,
            "initial_story_flags": map_metadata.initial_story_flags,
            "master_quest_registry": map_metadata.master_quest_registry,
            "global_behavior_triggers": hardened_triggers
        }

        # Idempotent compilation processing loops protecting master indexes
        existing_blueprint = await AdventureBlueprint.find_one(
            AdventureBlueprint.adventure_id == map_metadata.adventure_id
        )

        if existing_blueprint:
            await existing_blueprint.update({"$set": blueprint_data})
        else:
            new_blueprint = AdventureBlueprint(**blueprint_data)
            await new_blueprint.insert()

        print(f"🎉 [Phase 4] Blueprint for '{map_metadata.module_name}' compiled successfully.")
        return True
        
    except Exception as ex:
        print(f"❌ [Phase 4 Error] Critical failure writing compilation rules to blueprint schemas: {ex}")
        return False


# =====================================================================
# SYSTEM SERVICE RUNNER COROUTINE
# =====================================================================

async def ingest_campaign_module(target_md_path: Path) -> Dict[str, Any]:
    """
    Executes the decoupled multi-pass ingestion lifecycle engine rules synchronously.
    Returns tracking summaries mapping database process iterations.
    """
    if not target_md_path.exists():
        print(f"❌ Ingestion Error: Campaign markdown source file missing at: {target_md_path}")
        return {"status": "FILE_NOT_FOUND"}

    print(f"📖 Loading campaign source file: {target_md_path.name}...")
    adventure_text = target_md_path.read_text(encoding="utf-8")

    # Linear Phase Execution
    # Phase 1 - Map Discovery
    map_metadata = await _execute_map_discovery(adventure_text)

    # Phase 2 - Node Hydration
    hydrated_nodes = await _execute_reduce_hydration_sequential(map_metadata)

    # Phase 3 - Node Validation
    starting_node_id, repaired_links = await _validate_and_repair_topology(
        adventure_id=map_metadata.adventure_id, 
        node_array=hydrated_nodes
    )
    
    if not starting_node_id and hydrated_nodes:
        starting_node_id = hydrated_nodes[0].node_id
        print(f"⚠️ Topo Warning: No explicit CAMPAIGN_ROOT found. Fallback entry: {starting_node_id}")

    # Phase 4 - Blueprint Compilation
    blueprint_success = await _compile_master_blueprint(map_metadata, starting_node_id)
    
    if not blueprint_success:
        return {"status": "FAILED_BLUEPRINT_COMPILATION"}

    return {        
        "adventure_id": map_metadata.adventure_id,
        "status": "SUCCESS",
        "nodes_processed_count": len(hydrated_nodes),
        "synthesized_repair_stubs": repaired_links,
        "starting_node_id": starting_node_id
    }


if __name__ == "__main__":
    # Test script initialization loop entry
    async def main():
        await init_database()
        test_path = Path("database/seed/adventures/adventure.md")
        result = await ingest_campaign_module(test_path)
        print(f"Ingestion Finished: {json.dumps(result, indent=2)}")

    asyncio.run(main())