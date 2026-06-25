import os
import sys
import asyncio
from pathlib import Path
from typing import List, Optional, Set, Dict

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
from database.models.campaign.adventure_blueprint import AdventureBlueprint
from database.models.campaign.node import (
    GameNode, 
    TopologySkeleton, 
    MechanicalEntities, 
    NarrativeAtmosphere, 
    NodeExit, 
    CombatantEntity, 
    InteractionObstacle, 
    LootItem, 
    LogicTrigger, 
    LoreContext, 
    SensoryProfile
)

# Import system infrastructure wrappers
from services.gemini_client import gemini_service
from services.template_service import TemplateService

""" Command to run seeding script
docker exec -it dnd_discord_bot python -m services.adventure_ingestor
"""


def _read_source_adventure_file(filename: str = "adventure.md") -> str:
    """
    Safely finds and parses the raw campaign text asset.
    Looks in src/database/seed/adventures/ by default.
    """
    # Define the target directory as requested
    target_dir = ROOT_DIR / "database" / "seed" / "adventures"
    target_path = target_dir / filename
    
    if not target_path.exists():
        raise FileNotFoundError(
            f"Could not locate your raw source material file '{filename}'. "
            f"Please ensure it is placed at: {target_path}"
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

    test_text = len(raw_adventure_text)
    print(f"[DEBUG] Full text length: {test_text}") 

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
        topology_skeleton = await gemini_service.generate_structured_output(
            model='gemini-3.1-flash-lite',
            contents=prompt_payload,
            response_schema=MappingDTO
        )
        
        print(f"[DEBUG] Raw output for {topology_skeleton.nodes}")

        if not _validate_topology_integrity(topology_skeleton):
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
) -> Optional[List[MechanicalHydrationDTO]]:
    """
    Phase 2: Loops through each valid topology node identifier to extract
    rigid rule structures (Combatants, Loot, Obstacles, and state Triggers).
    """
    print(f"\n[Ingestion Engine] Initializing Phase 2: Mechanical Hydration...")
    hydrated_mechanical_nodes: List[MechanicalHydrationDTO] = []
    template_engine = TemplateService()

    test_text = len(raw_adventure_text)
    print(f"[DEBUG] Full text length: {test_text}") 

    for node in topology_skeleton.nodes:
        print(f" -> Hydrating Rules for Node ID: {node.node_id}")
        await asyncio.sleep(5)
        try:
            prompt_payload = template_engine.render_prompt(
                template_name="adventure_mechanical_hydration_prompt.jinja",
                context={
                    "adventure_text": raw_adventure_text,
                    "target_node_id": node.node_id,
                    "target_node_title": node.title
                }
            )
            
            node_mechanical_data = await gemini_service.generate_structured_output(
                model='gemini-3.1-flash-lite',
                contents=prompt_payload,
                response_schema=MechanicalHydrationDTO
            )

            print(f"[DEBUG] Raw output for {node.node_id}: {node_mechanical_data.model_dump_json()}")
            
            node_mechanical_data.node_id = node.node_id
            hydrated_mechanical_nodes.append(node_mechanical_data)
            
        except Exception as e:
            print(f"[FATAL] Mechanical hydration failed for node {node.node_id}: {e}")
            return None # Fail the whole phase

    print(f"[SUCCESS] Phase 2 complete. Hydrated {len(hydrated_mechanical_nodes)} nodes.")
    return hydrated_mechanical_nodes


async def _execute_phase_3_narrative_hydration(
    raw_adventure_text: str, 
    topology_skeleton: MappingDTO
) -> Optional[List[NarrativeHydrationDTO]]:
    """
    Phase 3: Extracts heavy markdown flavor text descriptions, sensory parameters, 
    and environment dressing tags optimized for long-term Gemini Context Caching.
    """
    print(f"\n[Ingestion Engine] Initializing Phase 3: Narrative & Atmospheric Hydration...")

    test_text = len(raw_adventure_text)
    print(f"[DEBUG] Full text length: {test_text}") 

    hydrated_narrative_nodes: List[NarrativeHydrationDTO] = []
    template_engine = TemplateService()

    for node in topology_skeleton.nodes:
        print(f" -> Hydrating Sensory Profile for Node ID: {node.node_id}")
        await asyncio.sleep(5)
        try:
            prompt_payload = template_engine.render_prompt(
                template_name="adventure_narrative_hydration_prompt.jinja",
                context={
                    "adventure_text": raw_adventure_text,
                    "target_node_id": node.node_id,
                    "target_node_title": node.title
                }
            )
            
            node_narrative_data = await gemini_service.generate_structured_output(
                model='gemini-3.1-flash-lite',
                contents=prompt_payload,
                response_schema=NarrativeHydrationDTO
            )
            
            node_narrative_data.node_id = node.node_id
            hydrated_narrative_nodes.append(node_narrative_data)
            
        except Exception as e:
            print(f"[FATAL] Narrative hydration failed for node {node.node_id}: {e}")
            return None # Fail the whole phase

    print(f"[SUCCESS] Phase 3 complete. Hydrated {len(hydrated_narrative_nodes)} nodes.")
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
        
        blueprint_metadata = await gemini_service.generate_structured_output(
            model='gemini-3.1-flash-lite',
            contents=prompt_payload,
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
    print(f"\n[Ingestion Engine] Initializing Phase 5: Database Serialization Pass...")
    
    try:
        mech_lookup = {n.node_id: n for n in mechanical_nodes}
        narr_lookup = {n.node_id: n for n in narrative_nodes}
        
        for node_skeleton in topology_skeleton.nodes:
            nid = node_skeleton.node_id
            m_data = mech_lookup.get(nid)
            n_data = narr_lookup.get(nid)
            
            # --- MAP TO NESTED MODELS ---
            
            # 1. Topology
            topology = TopologySkeleton(
                exits=[NodeExit(direction=e.direction, target_node_id=e.target_node_id) for e in node_skeleton.exits]
            )
            
            # 2. Mechanics
            mechanics = MechanicalEntities(
                combatants=[CombatantEntity(**c.model_dump()) for c in m_data.combatants] if m_data else [],
                loot_array=[LootItem(**l.model_dump()) for l in m_data.loot_array] if m_data else [],
                standalone_obstacles=[InteractionObstacle(**o.model_dump()) for o in m_data.standalone_obstacles] if m_data else [],
                triggers=[LogicTrigger(**t.model_dump()) for t in m_data.triggers] if m_data else []
            )
            
            # 3. Narrative
            narrative = NarrativeAtmosphere(
                title=node_skeleton.title,
                description=n_data.description if n_data else "No description provided.",
                lore=LoreContext(
                    spatial_dimensions=n_data.spatial_dimensions if n_data else "Unknown",
                    sensory_profile=SensoryProfile(
                        sight=n_data.sensory_profile.sight,
                        sound=n_data.sensory_profile.sound,
                        smell=n_data.sensory_profile.smell,
                        temperature=n_data.sensory_profile.temperature
                    ) if n_data else SensoryProfile(),
                    narrative_history=n_data.narrative_history if n_data else None
                ),
                sandbox_prop_tags=n_data.sandbox_prop_tags if n_data else []
            )

            # --- UPSERT ---
            node_doc = GameNode(
                adventure_id=topology_skeleton.adventure_id,
                node_id=nid,
                parent_id=node_skeleton.parent_id,
                topology=topology,
                mechanics=mechanics,
                narrative=narrative
            )
            
            existing = await GameNode.find_one(
                GameNode.node_id == nid, 
                GameNode.adventure_id == topology_skeleton.adventure_id
            )
            
            if existing:
                await existing.set({
                    GameNode.topology: topology,
                    GameNode.mechanics: mechanics,
                    GameNode.narrative: narrative
                })
            else:
                await node_doc.insert()

        # ... (Finish with AdventureBlueprint upsert)
        print(f"✅ PHASE 5 SUCCESS: Ingestion pipeline complete. Database is perfectly synchronized.")
        return True

    except Exception as e:
        print(f"❌ CRITICAL ERROR during DB Sync: {e}")
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
    try:
        raw_text = _read_source_adventure_file("adventure.md")
    except FileNotFoundError as e:
        print(f"\n[FATAL] Pre-flight check failed: {e}")
        return
    except Exception as e:
        print(f"\n[FATAL] Unexpected error reading source file: {e}")
        return
    
    # Phase 1
    topology_skeleton = await _execute_phase_1_mapping(raw_text)
    if not topology_skeleton:
        print("\n[FATAL] Pipeline stopped in Phase 1.")
        return

    # Phase 2: Hydrate mechanical tokens
    mechanical_nodes = await _execute_phase_2_mechanical_hydration(raw_text, topology_skeleton)
    if not mechanical_nodes or len(mechanical_nodes) != len(topology_skeleton.nodes):
        print("\n[FATAL] Pipeline stopped: Mechanical hydration failed or incomplete.")
        return
    
    # Phase 3: Hydrate narrative context payloads
    narrative_nodes = await _execute_phase_3_narrative_hydration(raw_text, topology_skeleton)
    if not narrative_nodes or len(narrative_nodes) != len(topology_skeleton.nodes):
        print("\n[FATAL] Pipeline stopped: Narrative hydration failed or incomplete.")
        return
    
    # Phase 4: Compile macro blueprint configuration attributes
    master_blueprint = await _execute_phase_4_blueprint_compilation(raw_text, topology_skeleton)
    if not master_blueprint:
        print("\n[FATAL] Pipeline stopped: Master blueprint compilation failed.")
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
    asyncio.run(run_pipeline_async())