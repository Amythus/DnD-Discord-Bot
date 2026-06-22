import os
import json
import asyncio
from pathlib import Path
from typing import List, Set, Tuple, Optional, Dict, Any

from database.connection import init_database  
from database.models.spatial.node import GameNode  
from database.models.campaign.adventure_blueprint import AdventureBlueprint
from database.schemas.node_dto import NodeDTO  
from database.schemas.adventure_dto import AdventureDTO
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
        "adventure_ingestion_prompt.jinja", 
        adventure_text=raw_text
    )

    map_response: AdventureMapDTO = await gemini_service.generate_structured_output(
        model='gemini-3.1-flash-lite',
        contents=compiled_prompt,
        response_schema=AdventureMapDTO
    )
    
    # Pre-populate the registry flat index for downstream context awareness
    map_response.node_registry = [item.node_id for item in map_response.discovered_nodes]
    
    print(f"✅ [Phase 1] Success: Discovered {len(map_response.discovered_nodes)} spatial layouts.")
    return map_response


async def _hydrate_single_node(adventure_id: str, discovered_item, node_registry: List[str]) -> Optional[NodeDTO]:
    """
    PHASE 2 WORKER: Submits a single node translation text slice to the LLM model.
    """
    template_engine = TemplateService()
    node_prompt = template_engine.render_prompt(
        "node_hydration_prompt.jinja",
        adventure_id=adventure_id,
        node_id=discovered_item.node_id,
        title=discovered_item.title,
        node_registry=node_registry,
        raw_text_segment=discovered_item.raw_text_segment
    )
    
    try:
        node_dto: NodeDTO = await gemini_service.generate_structured_output(
            model='gemini-3.1-flash-lite',
            contents=node_prompt,
            response_schema=NodeDTO
        )
        return node_dto
    except Exception as e:
        print(f"❌ [Phase 2] Structural extraction failure on Node '{discovered_item.node_id}': {e}")
        return None


async def _execute_reduce_hydration_sequential(map_metadata: AdventureMapDTO) -> List[NodeDTO]:
    """
    PHASE 2: Sequential Reduce Pass.
    Processes nodes one by one with a mandatory 6-second rate limit backoff.
    Performs non-destructive database patching to protect active runtime modifications.
    """
    print("🔗 [Phase 2] Starting sequential node hydration loop...")
    hydrated_nodes: List[NodeDTO] = []
    total_nodes = len(map_metadata.discovered_nodes)

    for idx, discovered in enumerate(map_metadata.discovered_nodes):
        current_num = idx + 1
        print(f"   ↳ Processing [{current_num}/{total_nodes}]: {discovered.node_id}")
        
        # Linear blocking request
        node_dto = await _hydrate_single_node(
            adventure_id=map_metadata.adventure_id,
            discovered_item=discovered,
            node_registry=map_metadata.node_registry
        )
        
        if node_dto:
            node_data = node_dto.model_dump()
            existing_node = await GameNode.find_one({
                "adventure_id": map_metadata.adventure_id,
                "node_id": node_dto.node_id
            })

            if existing_node:
                # Retain dynamic database overrides (e.g., fog of war, player state logs)
                preserved_state = getattr(existing_node, "room_states", {})
                preserved_discovery = getattr(existing_node, "discovered_by", [])
                
                updated_node = GameNode(**node_data)
                updated_node.id = existing_node.id
                
                if preserved_state:
                    updated_node.room_states = preserved_state
                if preserved_discovery:
                    updated_node.discovered_by = preserved_discovery
                    
                await updated_node.replace()
            else:
                new_node = GameNode(**node_data)
                await new_node.save()

            hydrated_nodes.append(node_dto)

        # 15 RPM Limit Guard: Apply a strict 6-second delay between requests
        if current_num < total_nodes:
            print(f"   ⏳ [Guard] Sleeping 6 seconds to stay below 15 RPM quota limit...")
            await asyncio.sleep(6.0)

    print(f"✅ [Phase 2] Sequential database sync complete. Integrated {len(hydrated_nodes)} nodes.")
    return hydrated_nodes


async def _validate_and_repair_topology(adventure_id: str, node_array: List[NodeDTO]) -> Tuple[Optional[str], int]:
    """
    PHASE 3: Topological Check & Graph Repair.
    Identifies broken paths. Synthesizes fallback stubs for missing nodes.
    """
    print("\n🛡️ [Phase 3] Auditing graph connectivity and running topological repairs...")
    
    processed_ids: Set[str] = {node.node_id for node in node_array}
    broken_links_count = 0
    starting_node_id = None

    for node in node_array:
        if node.node_type == "CAMPAIGN_ROOT":
            starting_node_id = node.node_id

        if hasattr(node, "navigation") and node.navigation:
            exits = getattr(node.navigation, "exits", [])
            for game_exit in exits:
                target = getattr(game_exit, "target_node_id", None)
                
                if target and target not in processed_ids:
                    print(f"  ⚠️ Topo Discontinuity: '{node.node_id}' points to missing target: '{target}'. Synthesizing fallback stub...")
                    broken_links_count += 1
                    
                    stub_node = GameNode(
                        adventure_id=adventure_id,
                        node_id=target,
                        title=f"Undiscovered Passage ({target.replace('_', ' ').title()})",
                        node_type="ROOM",
                        description="This path appears dark and unexplored. The spatial data was synthesized automatically via topological repair.",
                        parent_node_id=node.node_id
                    )
                    
                    existing_stub = await GameNode.find_one({"adventure_id": adventure_id, "node_id": target})
                    if not existing_stub:
                        await stub_node.save()
                        processed_ids.add(target)

    return starting_node_id, broken_links_count


async def _compile_master_blueprint(map_metadata: AdventureMapDTO, starting_node_id: str) -> bool:
    """
    PHASE 4: Blueprint Assembly.
    Compiles global variables non-destructively over active entries.
    """
    print("\n🏗️ [Phase 4] Assembling global adventure orchestration blueprint...")
    try:
        existing_blueprint = await AdventureBlueprint.find_one({
            "adventure_id": map_metadata.adventure_id
        })

        blueprint_data = {
            "adventure_id": map_metadata.adventure_id,
            "module_name": map_metadata.module_name,
            "starting_node_id": starting_node_id,
            "initiator_prompt": map_metadata.initiator_prompt,
            "default_npc_dispositions": map_metadata.default_npc_dispositions,
            "initial_story_flags": map_metadata.initial_story_flags,
            "master_quest_registry": map_metadata.master_quest_registry
        }

        if existing_blueprint:
            print(f"🔄 Syncing blueprint configurations cleanly...")
            live_blueprint = AdventureBlueprint(**blueprint_data)
            live_blueprint.id = existing_blueprint.id
            await live_blueprint.replace()
        else:
            print(f"💾 Saving new campaign master template blueprint to database...")
            live_blueprint = AdventureBlueprint(**blueprint_data)
            await live_blueprint.save()

        print(f"🚀 Master Campaign '{map_metadata.module_name}' is compiled successfully.")
        return True
    except Exception as e:
        print(f"❌ [Phase 4] Critical error writing campaign master blueprint: {e}")
        return False

# =====================================================================
# MAIN ENTRYPOINT
# =====================================================================

async def ingest_adventure(file_name: str = "adventure.md") -> dict:
    """
    Orchestration core driving the robust, sequential ingestion pipeline.
    """
    await init_database()

    script_dir = Path(__file__).parent
    target_md_path = script_dir / "adventures" / file_name
    if not target_md_path.exists():
        print(f"❌ Error: Targeted markdown source file missing at: {target_md_path}")
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


async def main():
    print("🔌 Initializing connection to MongoDB Cluster...")
    await ingest_adventure()

if __name__ == "__main__":
    asyncio.run(main())