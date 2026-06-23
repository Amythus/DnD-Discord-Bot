from enum import Enum
from beanie import Document, Indexed
from pydantic import BaseModel, Field, ConfigDict, field_validator
from pymongo import IndexModel, ASCENDING
from typing import List, Dict, Any, Optional

# =====================================================================
# SYSTEM COMPOSITION ENUMS (SHARED CASE-INSENSITIVE ENFORCED TAXONOMY)
# =====================================================================

class ExitType(str, Enum):
    OPEN_ARCHWAY = "OPEN_ARCHWAY"
    OPEN_THOROUGHFARE = "OPEN_THOROUGHFARE"
    WOODEN_DOOR = "WOODEN_DOOR"
    HEAVY_OAK_DOOR = "HEAVY_OAK_DOOR"
    IRON_DOOR = "IRON_DOOR"
    STONE_SLAB = "STONE_SLAB"
    PORTCULLIS = "PORTCULLIS"
    IRON_BARS = "IRON_BARS"
    HIDDEN_SECRET_DOOR = "HIDDEN_SECRET_DOOR"
    NATURAL_FISSURE = "NATURAL_FISSURE"
    MAGIC_BARRIER = "MAGIC_BARRIER"
    WINDOW = "WINDOW"

class ValidDirection(str, Enum):
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"
    NORTHEAST = "northeast"
    NORTHWEST = "northwest"
    SOUTHEAST = "southeast"
    SOUTHWEST = "southwest"
    UP = "up"
    DOWN = "down"
    ENTER = "enter"
    EXIT = "exit"
    INTERACTIVE = "INTERACTIVE"

class LightingType(str, Enum):
    DARKNESS = "DARKNESS"
    DIM_LIGHT = "DIM_LIGHT"
    BRIGHT_LIGHT = "BRIGHT_LIGHT"

class SafetyType(str, Enum):
    SAFE_COMFORTABLE = "SAFE_COMFORTABLE"
    UNSAFE_ALERT = "UNSAFE_ALERT"
    UNSAFE_DANGEROUS = "UNSAFE_DANGEROUS"

class NodeType(str, Enum):
    CAMPAIGN_ROOT = "CAMPAIGN_ROOT"
    CITY_OVERWORLD = "CITY_OVERWORLD"
    REGIONAL_DISTRICT = "REGIONAL_DISTRICT"
    BUILDING_POI = "BUILDING_POI"
    INTERIOR_ROOM = "INTERIOR_ROOM"

class FactionDisposition(str, Enum):
    FRIENDLY = "FRIENDLY"
    NEUTRAL = "NEUTRAL"
    HOSTILE = "HOSTILE"

# =====================================================================
# PURE REUSABLE STRUCTURAL SUB-MODELS (DRY BLOCKS)
# =====================================================================

class ExecutionEffect(BaseModel):
    effect_target: str = Field(
        description="The target state path to modify inside the system tracker (e.g., 'global_state.threat_level', 'node.navigation.exits.north.is_locked')."
    )
    set_value: Any = Field(
        description="The literal value, boolean, or script text applied to the target property when execution loops run."
    )

class SharedLootItem(BaseModel):
    item_id: str = Field(description="Unique snake_case identifier for this specific piece of gear, key, or treasure asset.")
    name: str = Field(description="The formal user-facing presentation name printed to players upon viewing.")
    description: str = Field(description="Detailed narrative framing what the asset looks like and its physical features.")

class Exit(BaseModel):
    direction: ValidDirection = Field(
        description="The primary movement vector relative to this room (e.g., 'north', 'enter')."
    )
    target_node_id: str = Field(
        description="The exact snake_case node_id destination string that this exit connects to. Must match an ID from the master index map."
    )
    exit_type: ExitType = Field(
        description="The physical composition and mechanical form of the path boundary or entry point."
    )
    description: str = Field(
        description="Detailed text clarifying what this egress looks like, including any visibility or material constraints."
    )
    is_locked: bool = Field(
        default=False, 
        description="Indicates whether the path requires a mechanical key, puzzle resolution, or lockpicking override to bypass."
    )
    lock_dc: Optional[int] = Field(
        default=None, 
        description="The numerical check threshold required to bypass this locked state using tools or force."
    )
    key_item_id: Optional[str] = Field(
        default=None, 
        description="The unique identification item string matching the inventory item required to instantly clear this locked state."
    )

    @field_validator('exit_type', mode='before')
    @classmethod
    def coerce_exit_type_uppercase(cls, v: Any) -> Any:
        return v.upper() if isinstance(v, str) else v

class NavigationGrid(BaseModel):
    map_layer: str = Field(
        description="The specific region category or dungeon floor tracking this location layer group (e.g., 'Lower Caverns')."
    )
    exits: List[Exit] = Field(
        default_factory=list, 
        description="An array of all structured navigation paths leading out of this node into adjacent graph boundaries."
    )

class EnvironmentProfile(BaseModel):
    lighting: LightingType = Field(
        description="The prevailing ambient light layer within this location, governing sight-based mechanics and perception checks."
    )
    resting_safety: SafetyType = Field(
        description="The security classification governing whether a player character can successfully take a short or long rest here."
    )
    dimensions: str = Field(
        description="The physical geometry of the space, tracking ceiling heights, room measurements, or layout boundaries as written in prose."
    )

    @field_validator('lighting', 'resting_safety', mode='before')
    @classmethod
    def coerce_env_uppercase(cls, v: Any) -> Any:
        return v.upper() if isinstance(v, str) else v

class SensoryProfile(BaseModel):
    visual_clue: str = Field(
        description="The prominent, immediate narrative visual feature printed to players immediately upon crossing into this node environment."
    )
    olfactory_clue: Optional[str] = Field(
        default=None, 
        description="A clear description of ambient smells, chemical odors, or air quality traits defining the atmosphere."
    )
    ambient_sound: Optional[str] = Field(
        default=None, 
        description="Persistent background noises, structural creaks, echoes, or auditory clues present in this location."
    )
    thermal_clue: Optional[str] = Field(
        default=None, 
        description="Micro-climate indicators tracking relative temperature variations (e.g., freezing drafts, stagnant humid heat)."
    )

class EncounterReference(BaseModel):
    creature_id: str = Field(
        description="The precise snake_case reference key tying this slot to a registered monster template block in your master codex."
    )
    quantity: int = Field(
        description="The aggregate volume of this specific creature class instantiated here when combat routines initialize."
    )
    is_procedural_table: bool = Field(
        default=False, 
        description="True if this encounter entity slot dynamically references a roll table index instead of a fixed creature asset."
    )

class NPCProfile(BaseModel):
    npc_id: str = Field(
        description="Unique snake_case tracking string representing this named character within your state engines."
    )
    name: str = Field(
        description="The clean formal display name used for interactive presentation blocks and dialogue headers."
    )
    disposition: FactionDisposition = Field(
        description="The initial political or faction alignment prioritizing how this character reacts to the active adventuring party."
    )
    short_description: str = Field(
        description="A concise physical and visual blurb framing the entity when closely viewed or introduced."
    )
    agenda: str = Field(
        description="The explicit motivation, hidden alignment, or mechanical drive determining their speech nodes and combat logic."
    )
    dialog_root_id: Optional[str] = Field(
        default=None, 
        description="The structural tracking identifier linking this actor directly to their conversation graph file."
    )

    @field_validator('disposition', mode='before')
    @classmethod
    def coerce_disposition_uppercase(cls, v: Any) -> Any:
        return v.upper() if isinstance(v, str) else v

class SpatialTrigger(BaseModel):
    trigger_id: str = Field(
        description="Unique snake_case tracking token mapping this reactive script event to an operation context loop."
    )
    conditions: List[str] = Field(
        description="A collection of evaluate-ready conditional states that instantly fire this trigger (e.g., ['party_inspects_altar == true'])."
    )
    execution_effects: List[ExecutionEffect] = Field(
        description="A sequence outlining the system target property changes applied upon trigger execution."
    )

class EnvironmentalTrap(BaseModel):
    trap_id: str = Field(
        description="Unique structural snake_case tracker for this localized hazard or mechanical trap."
    )
    name: str = Field(
        description="The clean display title of the environmental danger printed to players upon identification."
    )
    detection_dc: int = Field(
        description="The raw physical Investigation or Perception score necessary to view this hazard before it accidentally activates."
    )
    disarm_mechanism: str = Field(
        description="Concrete narrative instructions and check requirements defining how a character safely defuses or disables the threat."
    )
    mechanical_effect: str = Field(
        description="The exact mechanical expression of the trap when triggered, outlining damage dice expressions, save types, and DCs."
    )

class TimedEvent(BaseModel):
    event_id: str = Field(
        description="Unique tracking string for time-delayed or phased sequence shifts within the room ecosystem."
    )
    turn_interval: int = Field(
        description="The absolute continuous turn count or timer cycle frequency that checks and executes this dynamic state change."
    )
    execution_effects: List[ExecutionEffect] = Field(
        description="The structured list of mutations or event updates applied globally when the interval target triggers."
    )

class LocalInteractable(BaseModel):
    interactable_id: str = Field(
        description="Unique snake_case id representing a physics-bound or manipulable entity object (e.g., 'heavy_iron_chest_02')."
    )
    name: str = Field(
        description="Clean user-facing display name identifying this sandbox prop on player inspection matrices."
    )
    description: str = Field(
        description="Detailed narrative text illustrating what this item is and its orientation within the scene."
    )
    interaction_effect: str = Field(
        description="The text feedback returned to the chat log upon basic character inspection or simple handling."
    )
    execution_effects: List[ExecutionEffect] = Field(
        default_factory=list,
        description="Optional structural modifications kicked off inside the database layer upon successful interaction execution."
    )

class LocalQuestHook(BaseModel):
    quest_id: str = Field(
        description="The system-wide relational lookup token identifying a parent entry inside your campaign quest log data collection."
    )
    status_on_dispatch: str = Field(
        description="The initial operational baseline state pushed to the player log upon interaction (e.g., 'AVAILABLE', 'ACTIVE')."
    )
    narrative_trigger_blurb: str = Field(
        description="Flavor text or milestone notification displayed directly to the players indicating quest state advancement."
    )

class LocalTreasure(BaseModel):
    gold_pool: Optional[int] = Field(
        default=0, 
        description="The currency total stored loosely within containers or scattered objects throughout this node layer."
    )
    items: List[SharedLootItem] = Field(
        default_factory=list, 
        description="An array of explicit custom item blueprints located inside local chests, hidden stashes, or loot containers."
    )

class NodeMetadata(BaseModel):
    explicit_props: List[str] = Field(
        default_factory=list, 
        description="A list of physical objects natively present inside this node landscape (e.g., ['rubble piles', 'old tapestries'])."
    )
    sandbox_prop_tags: List[str] = Field(
        default_factory=list, 
        description="Tracking tags used for sandbox procedural lookup arrays and interaction routers (e.g., ['stone', 'flammable'])."
    )
    procedural_traversal_allowed: bool = Field(
        default=True, 
        description="True if automated bot search configurations or pathfinding agents can route through this room without prerequisite events."
    )
    parent_alert_flags: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Local notification toggles connected straight to wider regional faction alert tracking maps."
    )

class LLMContexts(BaseModel):
    baseline_narration: str = Field(
        description="The atmospheric, highly immersive introductory text chunk outputted to players immediately when entering this zone."
    )

# =====================================================================
# PERSISTENT BEANIE ODM DATABASE DOCUMENT MODEL
# =====================================================================

class GameNode(Document):
    """
    Persistent MongoDB model tracking a static world location.
    Structures specialized data matrices matching downstream ingestion passes.
    """
    adventure_id: Indexed(str) = Field(description="The core grouping ID anchoring this node to a specific campaign book layer.")
    node_id: Indexed(str) = Field(description="The explicit localized identification string, structured uniformly in snake_case.")
    parent_node_id: Optional[str] = Field(default=None, description="Relational pointer up to a broader regional layout or macro-node.")
    node_type: NodeType = Field(description="The architectural layer category of this location.")
    title: str = Field(description="The user-facing clean title shown to players in Discord embeds.")
    
    navigation: NavigationGrid = Field(description="The entry and exit connections tracking spatial graph directions.")
    environment: EnvironmentProfile = Field(description="The environmental variables dictating underlying mechanics.")
    sensory_profile: SensoryProfile = Field(description="The atmospheric sensory data feeding the parser interface.")
    
    encounters: List[EncounterReference] = Field(default_factory=list)
    npc_profiles: List[NPCProfile] = Field(default_factory=list)
    interactables: List[LocalInteractable] = Field(default_factory=list)
    
    spatial_triggers: List[SpatialTrigger] = Field(default_factory=list)
    environmental_traps: List[EnvironmentalTrap] = Field(default_factory=list)
    timed_events: List[TimedEvent] = Field(default_factory=list)
    
    story_hooks: List[str] = Field(default_factory=list)
    quests: List[LocalQuestHook] = Field(default_factory=list)
    campaign_lore: List[str] = Field(default_factory=list)
    treasure: LocalTreasure = Field(default_factory=lambda: LocalTreasure())
    
    node_metadata: NodeMetadata = Field(description="Systemic tracking metadata organizing infrastructure properties.")
    llm_contexts: LLMContexts = Field(description="Pre-compiled narrative text variants providing context for bot generation loops.")

    @field_validator('node_type', mode='before')
    @classmethod
    def coerce_node_type_uppercase(cls, v: Any) -> Any:
        return v.upper() if isinstance(v, str) else v

    class Settings:
        name = "game_nodes"
        indexes = [
            IndexModel([("adventure_id", ASCENDING), ("node_id", ASCENDING)], unique=True)
        ]