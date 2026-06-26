import os
import json
import asyncio
from pathlib import Path
from typing import List, Set, Tuple, Optional, Dict, Any

from database.connection import init_database  
from database.models.campaign.adventure_node import GameNode  
from database.models.campaign.adventure_blueprint import AdventureBlueprint
from database.schemas.node_dto import NodeDTO  
from database.schemas.mapping_dto import AdventureMapDTO, NodeDiscoveryItem
from database.schemas.node_mechanical_dto import NodeMechanicalDTO
from database.schemas.node_narrative_dto import NodeNarrativeDTO

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

    # 1. Collect all registered IDs
    registered_ids = {node.node_id for node in map_metadata.discovered_nodes}
    
    # 2. Check for broken links
    broken_links = []
    for node in map_metadata.discovered_nodes:
        # Note: Depending on your current schema, you might need to extract 
        # exit IDs directly from the text segments or an edges property.
        # This is pseudo-code for the logic:
        # for exit in node.exits:
        #     if exit.target_node_id not in registered_ids:
        #         broken_links.append(f"{node.node_id} -> {exit.target_node_id}")

    if broken_links:
        print(f"❌ Map Discovery Failed: Found dangling references: {broken_links}")
        raise ValueError("Invalid Topology: LLM generated links to non-existent nodes.")
        
    return map_metadata


async def _execute_reduce_hydration_sequential(map_metadata: AdventureMapDTO) -> List[NodeDTO]:
    """
    PHASE 2: Reduce Pass (Hydration Loops).
    Iterates sequentially over discovered node segments with strict rate-limit protection.
    """
    print(f"⚡ [Phase 2] Launching sequential hydration loops over {len(map_metadata.discovered_nodes)} items...")
    template_engine = TemplateService()
    hydrated_nodes = []

    for idx, item in enumerate(map_metadata.discovered_nodes, start=1):
        
        try:
            # PASS 1: Mechanical
            print(f"⏳ [{idx}/{len(map_metadata.discovered_nodes)}] Mehanical Hydration: {item.title} | (1/2)")
            mech_prompt = template_engine.render_prompt("node_mechanical.jinja", raw_text=item.raw_text_segment)
            mechanical = await gemini_service.generate_structured_output(
                model='gemini-3.1-flash-lite', contents=mech_prompt, response_schema=NodeMechanicalDTO
            )

            await asyncio.sleep(4.0) # Throttling

            # PASS 2: Narrative
            print(f"⏳ [{idx}/{len(map_metadata.discovered_nodes)}] Narrative Hydration: {item.title} | (2/2)")
            narr_prompt = template_engine.render_prompt("node_narrative.jinja", raw_text=item.raw_text_segment)
            narrative = await gemini_service.generate_structured_output(
                model='gemini-3.1-flash-lite', contents=narr_prompt, response_schema=NodeNarrativeDTO
            )
    
            node_type = "INTERIOR_ROOM" # Default value

            # Assemble DTO with data from both passes
            node_dto = NodeDTO(
                adventure_id=map_metadata.adventure_id,
                node_id=item.node_id,
                node_type=node_type,
                title=narrative.title,
                
                # Mechanical Mapping
                navigation=mechanical.navigation,
                environment=mechanical.environment,
                encounters=mechanical.encounters,
                spatial_triggers=mechanical.spatial_triggers,
                environmental_traps=mechanical.environmental_traps,
                treasure=mechanical.treasure,
                node_metadata=mechanical.node_metadata,
                
                # Narrative Mapping
                sensory_profile=narrative.sensory_profile,
                npc_profiles=narrative.npc_profiles,
                story_hooks=narrative.story_hooks,
                quests=narrative.quests,
                campaign_lore=narrative.campaign_lore,
                llm_contexts=narrative.llm_contexts
            )
            hydrated_nodes.append(node_dto)
            
        except Exception as e:
            # Fault Isolation: Log specific failure and move to next node
            print(f"❌ Failed to hydrate {item.node_id}: {str(e)}")
            continue 

        await asyncio.sleep(4.0) # Throttling

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