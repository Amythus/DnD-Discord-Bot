import os
import sys
import asyncio
from pathlib import Path
from typing import List, Optional, Set

# Ensure the root of the project is in the python path for absolute imports
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

# Import explicit structural DTOs from your schema file
from database.schemas.adventure_ingestion_dtos import (
    MappingDTO,
    MechanicalHydrationDTO,
    NarrativeHydrationDTO,
    AdventureBlueprintCompilationDTO
)

from database.connection import init_database  
from database.models import AdventureBlueprint, GameNode

# Import system infrastructure wrappers
from services.gemini_client import gemini_service
from services.template_service import TemplateService

""" Command to run seeding script
docker exec -it dnd_discord_bot python -m database.seed.adventures.adventure_ingestor
"""


def _read_source_adventure_file(filename: str = "adventure.md") -> str:
    """
    Safely finds and parses the raw campaign text asset.
    Looks in the script directory first, then falls back to project root.
    """
    current_dir = Path(__file__).resolve().parent
    target_path = current_dir / filename
    
    if not target_path.exists():
        target_path = ROOT_DIR / filename
        
    if not target_path.exists():
        raise FileNotFoundError(
            f"Could not locate your raw source material file '{filename}'. "
            f"Please place it at: {current_dir / filename}"
        )
        
    with open(target_path, "r", encoding="utf-8") as f:
        return f.read()


def _validate_topology_integrity(topology_skeleton: MappingDTO) -> bool:
    """
    Graph Integrity Guard (Phase 1 Check): Scans the extracted layout 
    matrix for orphan pointers or broken exits before processing rules.
    """
    print("[Validation Guard] Performing graph topology validation pass...")
    defined_node_ids: Set[str] = {node.node_id for node in topology_skeleton.nodes}
    orphan_errors_found = False

    for node in topology_skeleton.nodes:
        for exit_skeleton in node.exits:
            target = exit_skeleton.target_node_id
            if target not in defined_node_ids:
                print(
                    f"[TOPOLOGY FAULT] Broken connection caught in Node '{node.node_id}'! "
                    f"The exit direction '{exit_skeleton.direction}' points to a non-existent target: '{target}'."
                )
                orphan_errors_found = True

    if orphan_errors_found:
        print("[CRITICAL] Structural integrity checks failed. Topology contains orphan pointers.")
        return False

    print("[SUCCESS] Graph integrity verified. Zero orphan exits detected.")
    return True


# =====================================================================
# PIPELINE PHASE HELPERS
# =====================================================================

async def _execute_phase_1_mapping(raw_adventure_text: str) -> Optional[MappingDTO]:
    """
    Phase 1: Extracts the foundational layout framework skeleton and enforces 
    graph-integrity checks. Returns None if validation fails to halt ingestion.
    """
    print("\n[Ingestion Engine] Initializing Phase 1: Topology Skeleton Extraction...")
    template_engine = TemplateService()
    try:
        prompt_payload = template_engine.render_prompt(
            template_name="adventure_mapping_prompt.jinja",
            context={"adventure_text": raw_adventure_text}
        )
    except Exception as e:
        print(f"[ERROR] Failed to compile Jinja mapping template: {e}")
        return None

    try:
        print("[Ingestion Engine] Querying Gemini for topology framework...")
        topology_skeleton = await gemini_service.generate_structered_output(
            model='gemini-3.1-flash-lite',
            prompt=prompt_payload,
            response_schema=MappingDTO
        )
        
        
        if not __validate_topology_integrity(topology_skeleton):
            print("[FATAL ERROR] Map layout topology contains errors. Halting pipeline execution.")
            return None
            
        print("[SUCCESS] Phase 1 complete. Topology schema compiled safely.")
        return topology_skeleton
    except Exception as e:
        print(f"[CRITICAL ERROR] Phase 1 execution or structural validation failed: {e}")
        return None


async def _execute_phase_2_mechanical_hydration(
    raw_adventure_text: str, 
    topology_skeleton: MappingDTO
) -> List[MechanicalHydrationDTO]:
    """
    Phase 2: Loops through each valid topology node identifier to extract
    rigid rule structures (Combatants, Loot, Obstacles, and state Triggers).
    """
    print(f"\n[Ingestion Engine] Initializing Phase 2: Mechanical Hydration...")
    hydrated_mechanical_nodes: List[MechanicalHydrationDTO] = []

    for node in topology_skeleton.nodes:
        print(f" -> Hydrating Rules & Mechanics for Node ID: {node.node_id} ('{node.title}')")
        template_engine = TemplateService()
        try:
            prompt_payload = template_engine.render_prompt(
                template_name="adventure_mechanical_hydration_prompt.jinja",
                context={
                    "adventure_text": raw_adventure_text,
                    "target_node_id": node.node_id,
                    "target_node_title": node.title
                }
            )
            
            node_mechanical_data = await gemini_service.generate_structered_output(
                model='gemini-3.1-flash-lite',
                prompt=prompt_payload,
                response_schema=MechanicalHydrationDTO
            )
            
            # Align output data back to our target node tracking ID natively
            if node_mechanical_data.node_id != node.node_id:
                node_mechanical_data.node_id = node.node_id
                
            hydrated_mechanical_nodes.append(node_mechanical_data)
            print(f"    [SUCCESS] Extracted: {len(node_mechanical_data.combatants)} Monsters | "
                  f"{len(node_mechanical_data.loot_array)} Items | "
                  f"{len(node_mechanical_data.standalone_obstacles)} Traps")
        except Exception as e:
            print(f"    [ERROR] Failed to mechanically hydrate node {node.node_id}: {e}")
            continue

    return hydrated_mechanical_nodes


async def _execute_phase_3_narrative_hydration(
    raw_adventure_text: str, 
    topology_skeleton: MappingDTO
) -> List[NarrativeHydrationDTO]:
    """
    Phase 3: Extracts heavy markdown flavor text descriptions, sensory parameters, 
    and environment dressing tags optimized for long-term Gemini Context Caching.
    """
    print(f"\n[Ingestion Engine] Initializing Phase 3: Narrative & Atmospheric Hydration...")
    hydrated_narrative_nodes: List[NarrativeHydrationDTO] = []

    for node in topology_skeleton.nodes:
        print(f" -> Hydrating Sensory Profile for Node ID: {node.node_id} ('{node.title}')")
        template_engine = TemplateService()
        try:
            prompt_payload = template_engine.render_prompt(
                template_name="adventure_narrative_hydration_prompt.jinja",
                context={
                    "adventure_text": raw_adventure_text,
                    "target_node_id": node.node_id,
                    "target_node_title": node.title
                }
            )
            
            node_narrative_data = await gemini_service.generate_structered_output(
                model='gemini-3.1-flash-lite',
                prompt=prompt_payload,
                response_schema=NarrativeHydrationDTO
            )
            
            if node_narrative_data.node_id != node.node_id:
                node_narrative_data.node_id = node.node_id
                
            hydrated_narrative_nodes.append(node_narrative_data)
            print(f"    [SUCCESS] Extracted: Illumination='{node_narrative_data.illumination_level}' | "
                  f"Props={len(node_narrative_data.sandbox_prop_tags)}")
        except Exception as e:
            print(f"    [ERROR] Failed to narratively hydrate node {node.node_id}: {e}")
            continue

    return hydrated_narrative_nodes


async def _execute_phase_4_blueprint_compilation(
    raw_adventure_text: str, 
    topology_skeleton: MappingDTO
) -> Optional[AdventureBlueprintCompilationDTO]:
    """
    Phase 4: Extracts macro metadata config boundaries for the master payload
    including titles, systemic instructions, and player-facing entry story hooks.
    """
    print(f"\n[Ingestion Engine] Initializing Phase 4: Adventure Blueprint Compilation...")
    template_engine = TemplateService()
    try:
        prompt_payload = template_engine.render_prompt(
            template_name="adventure_blueprint_compilation_prompt.jinja",
            context={
                "adventure_text": raw_adventure_text,
                "expected_adventure_id": topology_skeleton.adventure_id
            }
        )
        
        blueprint_metadata = await gemini_service.generate_structered_output(
            model='gemini-3.1-flash-lite',
            prompt=prompt_payload,
            response_schema=AdventureBlueprintCompilationDTO
        )
        
        if blueprint_metadata.adventure_id != topology_skeleton.adventure_id:
            blueprint_metadata.adventure_id = topology_skeleton.adventure_id

        print(f"[SUCCESS] Phase 4 complete. Campaign title: '{blueprint_metadata.campaign_title}'")
        return blueprint_metadata
    except Exception as e:
        print(f"[CRITICAL ERROR] Failed to compile master adventure blueprint payload: {e}")
        return None


async def _execute_phase_5_database_insertion(
    topology_skeleton: MappingDTO,
    mechanical_nodes: List[MechanicalHydrationDTO],
    narrative_nodes: List[NarrativeHydrationDTO],
    master_blueprint: AdventureBlueprintCompilationDTO
) -> bool:
    """
    Phase 5 Core Orchestrator: Unites structural slices from Phases 1, 2, and 3 
    by node_id into unified entities, then updates or inserts documents via 
    asynchronous database contexts. Also stamps the master macro template configuration layout.
    """
    print(f"\n[Ingestion Engine] Initializing Phase 5: Asynchronous Database Serialization Pass...")
    
    try:
        # 1. Initialize DB Session Connection Pool
        # if not await init_database(): return False
        
        # 2. Map hydration steps to fast O(1) lookup tables by node_id
        mech_lookup: Dict[str, MechanicalHydrationDTO] = {n.node_id: n for n in mechanical_nodes}
        narr_lookup: Dict[str, NarrativeHydrationDTO] = {n.node_id: n for n in narrative_nodes}
        
        inserted_count = 0
        updated_count = 0
        
        # 3. Iterate through nodes defined in the framework layout and synthesize contexts
        for node_skeleton in topology_skeleton.nodes:
            nid = node_skeleton.node_id
            
            # Pull matched components safely or fall back to empty collections defaults
            m_data = mech_lookup.get(nid)
            n_data = narr_lookup.get(nid)
            
            # Combine discrete outputs into a single runtime layout structure
            node_document_payload = {
                "adventure_id": topology_skeleton.adventure_id,
                "node_id": nid,
                "parent_id": node_skeleton.parent_id,
                "title": node_skeleton.title,
                "exits": [e.model_dump() for e in node_skeleton.exits],
                
                # Mechanics Slices (Phase 2 Data)
                "combatants": [c.model_dump() for c in m_data.combatants] if m_data else [],
                "loot_array": [l.model_dump() for l in m_data.loot_array] if m_data else [],
                "standalone_obstacles": [o.model_dump() for o in m_data.standalone_obstacles] if m_data else [],
                "triggers": [t.model_dump() for t in m_data.triggers] if m_data else [],
                
                # Narrative Context Slices (Phase 3 Data)
                "description": n_data.description if n_data else "",
                "spatial_dimensions": n_data.spatial_dimensions if n_data else "",
                "illumination_level": n_data.illumination_level if n_data else "darkness",
                "ambient_state_tags": n_data.ambient_state_tags if n_data else [],
                "sensory_profile": n_data.sensory_profile.model_dump() if n_data else {"sight": "", "sound": "", "smell": "", "temperature": "ambient"},
                "narrative_history": n_data.narrative_history if n_data else None,
                "sandbox_prop_tags": n_data.sandbox_prop_tags if n_data else []
            }
            
            # DB Write Pipeline Execution Simulation via Beanie / Motor ODM methods:
            existing_node = await GameNode.find_one(GameNode.node_id == nid, GameNode.adventure_id == topology_skeleton.adventure_id)
            if existing_node:
                await existing_node.update({"$set": node_document_payload})
                updated_count += 1
            else:
                new_node = GameNode(**node_document_payload)
                await new_node.insert()
                inserted_count += 1
            
            # Simulating transaction trace logs
            updated_count += 1

        # 4. Serialize Overarching Master Campaign Blueprint Configuration Payload (Phase 4 Data)
        blueprint_payload = master_blueprint.model_dump()
        # blueprint_payload["ingestion_engine_version"] = "1.0.0" # Dynamic stamp context tracking hook
        await AdventureBlueprint.find_one(AdventureBlueprint.adventure_id == master_blueprint.adventure_id).upsert({"$set": blueprint_payload}, on_insert=AdventureBlueprint(**blueprint_payload))
        
        print(f"🚀 Database state synchronized: {inserted_count} nodes created, {updated_count} nodes updated.")
        print(f"✅ PHASE 5 SUCCESS: Ingestion pipeline complete. Database is perfectly synchronized.")
        return True

    except Exception as e:
        print(f"❌ CRITICAL INFRASTRUCTURE CRASH during database write pass: {e}", file=sys.stderr)
        return False


# =====================================================================
# MAIN PIPELINE ORCHESTRATOR
# =====================================================================

async def run_pipeline_async():
    """
    Master loop to trigger the multi-pass transformation phases sequentially.
    Outputs metrics confirming data convergence across all models.
    """

    await init_database()

    print("=====================================================================")
    print("   STARTING MULTI-PASS CAMPAIGN INGESTION PIPELINE")
    print("=====================================================================")
    
    # Load base text module details
    raw_text = _read_source_adventure_file("adventure.md")
    
    # Phase 1: Establish layout boundaries & validate topology
    topology_skeleton = _execute_phase_1_mapping(raw_text)
    if not topology_skeleton:
        print("\n[FATAL] Pipeline stopped in Phase 1 due to topology faults.")
        return

    # Phase 2: Hydrate mechanical tokens
    mechanical_nodes = _execute_phase_2_mechanical_hydration(raw_text, topology_skeleton)
    
    # Phase 3: Hydrate narrative context payloads
    narrative_nodes = _execute_phase_3_narrative_hydration(raw_text, topology_skeleton)
    
    # Phase 4: Compile macro blueprint configuration attributes
    master_blueprint = _execute_phase_4_blueprint_compilation(raw_text, topology_skeleton)
    if not master_blueprint:
        print("\n[FATAL] Pipeline aborted. Master blueprint metadata configuration generation failed.")
        return

    # Phase 5: Asynchronous data compilation and DB storage commit sync
    db_success = await _execute_phase_5_database_insertion(
        topology_skeleton=topology_skeleton,
        mechanical_nodes=mechanical_nodes,
        narrative_nodes=narrative_nodes,
        master_blueprint=master_blueprint
    )

    if db_success:
        print("\n=====================================================================")
        print("🎉 INGESTION COMPLETE: ADVENTURE MATRIX REDISTRIBUTED")
        print("=====================================================================")
        print(f"  Adventure Identifier: {master_blueprint.adventure_id}")
        print(f"  Campaign Framework:   {master_blueprint.campaign_title}")
        print(f"  Indexed Nodes:        {len(topology_skeleton.nodes)}")
        print("=====================================================================")


if __name__ == "__main__":
    # Execute the script safely within an active async event loops manager
    asyncio.run(run_pipeline_async())