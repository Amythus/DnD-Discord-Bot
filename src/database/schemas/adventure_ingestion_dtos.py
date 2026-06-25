from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict

# =====================================================================
# PHASE 1: TOPOLOGY SKELETON EXTRACTION DTO
# =====================================================================

class NodeExitSkeletonDTO(BaseModel):
    """Simplified directional exit for global map ingestion."""
    model_config = ConfigDict(extra="forbid")

    direction: str = Field(
        ..., 
        description="Direction/command text. Stick strictly to lowercase standard vectors or explicit short phrases.",
        examples=["north", "south", "down", "secret_door", "iron_ladder"]
    )
    target_node_id: str = Field(
        ..., 
        description="Target destination snake_case node identifier.",
        examples=["cragmaw_entrance", "goblin_blind_area_2"]
    )


class SingleNodeSkeletonDTO(BaseModel):
    """Minimalistic structure to build the map layout matrix framework."""
    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(
        ..., 
        description="Unique snake_case identifier for this specific area/room.",
        examples=["area_1_cave_mouth", "twin_pools_cave"]
    )
    parent_id: Optional[str] = Field(
        None, 
        description="Optional parent region, level, or overarching map section key.",
        examples=["cragmaw_hideout", "dungeon_level_1"]
    )
    title: str = Field(..., description="Short user-facing title/name of the room.")
    exits: List[NodeExitSkeletonDTO] = Field(default_factory=list)


class MappingDTO(BaseModel):
    """The root payload schema for Pass 1: Maps out the entire campaign structure in one go."""
    model_config = ConfigDict(extra="forbid")

    adventure_id: str = Field(
        ..., 
        description="Global snake_case unique ID for the adventure module.",
        examples=["lost_mine_of_phandelver", "curse_of_strahd"]
    )
    nodes: List[SingleNodeSkeletonDTO] = Field(..., description="Full array of all discovered spatial nodes.")


# =====================================================================
# PHASE 2: MECHANICAL HYDRATION DTO (Per-Node Extraction)
# =====================================================================

class IngestionCombatantDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_template_key: str = Field(..., description="Catalog reference string identifying the monster/NPC type.")
    quantity: int = Field(..., description="Headcount integer.")
    narrative_position: str = Field(..., description="What they are actively doing and where they are placed in the scene.")


class IngestionObstacleDTO(BaseModel):
    """Flattens out generic environmental challenges, traps, or stuck doors."""
    model_config = ConfigDict(extra="forbid")

    description: str = Field(..., description="Verbatim physical layout details and location in the area.")
    resolution_criteria: str = Field(..., description="Prose detailing how tools, backgrounds, or spells bypass this obstacle.")
    dc_baseline: int = Field(..., description="Target Difficulty Class baseline integer.")
    failure_consequences: Optional[str] = Field(None, description="Prose consequences for triggering or failing the check.")
    engine_callback_key: Optional[str] = Field(
        None, 
        description="Snake_case identifier matching backend scripts if middleware logic handles state changes.",
        examples=["tripwire_rockfall_trap", "rusty_iron_gate_lock"]
    )


class IngestionLootDTO(BaseModel):
    """Flattens out reward structures to prevent deep nesting complexity for the extraction model."""
    model_config = ConfigDict(extra="forbid")

    description: str = Field(..., description="Name or description of the treasure/reward item.")
    gp_value: int = Field(0, description="Estimated gold piece baseline value.")
    value_notes: Optional[str] = Field(None, description="Appraisal subtleties or contextual importance details.")
    loot_source_or_location: str = Field(..., description="Where the item is hidden or who has it.")
    discovery_criteria: str = Field(..., description="Prose detailing observation or search thresholds required to expose it.")
    guarded_by_obstacle_description: Optional[str] = Field(
        None, 
        description="If this loot item specifically requires resolving a localized obstacle/trap first, copy its brief details here."
    )


class IngestionTriggerDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adjudicator_narrative_condition: str = Field(..., description="Plain-text rule condition checked by the Adjudicator out-of-band.")
    engine_callback_key: str = Field(
        ..., 
        description="Snake_case identifier triggering Python state overrides or queue pauses.",
        examples=["pause_queue_for_stealth_check", "trigger_flood_sequence"]
    )


class MechanicalHydrationDTO(BaseModel):
    """Target schema for Pass 2: Executed node-by-node (or block-by-block) to seed interactions."""
    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(..., description="The matching snake_case identifier from Pass 1.")
    combatants: List[IngestionCombatantDTO] = Field(default_factory=list)
    loot_array: List[IngestionLootDTO] = Field(default_factory=list)
    standalone_obstacles: List[IngestionObstacleDTO] = Field(default_factory=list)
    triggers: List[IngestionTriggerDTO] = Field(default_factory=list)


# =====================================================================
# PHASE 3: NARRATIVE & ATMOSPHERIC HYDRATION DTO (Per-Node Extraction)
# =====================================================================

class IngestionSensoryProfileDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sight: str = Field("", description="Visual elements layout description.")
    sound: str = Field("", description="Environmental noise, echoes, or ambient sound profiles.")
    smell: str = Field("", description="Olfactory markers present in the local room.")
    temperature: str = Field(
        "ambient", 
        description="Thermal state notes framing the microclimate.",
        examples=["freezing and damp", "stifling heat", "ambient", "cool drafts"]
    )


class NarrativeHydrationDTO(BaseModel):
    """Target schema for Pass 3: Collects bulk token layers designed for Gemini Context Caching."""
    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(..., description="The matching snake_case identifier from Pass 1.")
    description: str = Field(..., description="Verbatim markdown flavor text describing the room to the players.")
    spatial_dimensions: str = Field(
        ..., 
        description="Room shape, height, and geometry specifications.",
        examples=["20x30ft rectangle with a 15ft vaulted ceiling", "Roughly circular cave basin, 40ft diameter"]
    )
    sensory_profile: IngestionSensoryProfileDTO = Field(..., description="Scrubbed multi-sensory variables.")
    narrative_history: Optional[str] = Field(None, description="Static lore, creator records, or past context events.")
    sandbox_prop_tags: List[str] = Field(
        default_factory=list, 
        description="List of implicit backdrop objects inferred for theatre-of-the-mind interactivity.",
        examples=[["wooden_benches", "iron_braziers", "loose_rubble"]]
    )


# =====================================================================
# PHASE 4: ADVENTURE COMPILER METADATA PAYLOAD DTO
# =====================================================================

class AdventureBlueprintCompilationDTO(BaseModel):
    """Supplied along with aggregated Pass 1-3 documents to finalize the parent configuration."""
    model_config = ConfigDict(extra="forbid")

    adventure_id: str = Field(..., description="Global snake_case unique ID matching Pass 1.")
    campaign_title: str = Field(..., description="The clean user-facing name of the overarching campaign.")
    initiator_prompt: str = Field(..., description="AI-facing systemic setup anchoring world-parsing logic boundaries.")
    story_hook: str = Field(..., description="Player-facing introductory splash narrative printed to Discord on session launch.")