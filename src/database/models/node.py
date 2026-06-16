from enum import Enum
from beanie import Document, Indexed
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Annotated, Literal

# ==========================================
# 1. NAVIGATION TAXONOMY ENUMS & SUB-MODELS
# ==========================================

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

ValidDirection = Literal["north", "south", "east", "west", "northeast", "northwest", "southeast", "southwest", "up", "down", "enter", "exit"]

class ExitVector(BaseModel):
    direction: ValidDirection = Field(
        description="The structural compass heading, verticality indicator, or spatial vector representing the entry/exit point."
    )
    type: ExitType = Field(
        description="The physical or magical taxonomy classification of this specific traversal boundary obstacle."
    )
    target_node_id: str = Field(
        description="The deterministic snake_case ID of the destination world_node this edge connects to (e.g., 'cragmaw_hideout_room_02')."
    )
    is_open: bool = Field(
        default=True, 
        description="Initial runtime boolean tracking state. True if unobstructed (archways or open doors), False if blocked."
    )
    is_locked: bool = Field(
        default=False, 
        description="True if the exit requires a mechanical key, magic word, or active lockpicking check to transition to an open state."
    )
    is_discovered: bool = Field(
        default=True, 
        description="False if this is a hidden secret door, concealed hatch, or obscure egress that requires an active skill check to find."
    )
    lock_dc: Optional[int] = Field(
        default=None, 
        description="The standard D&D Difficulty Class integer (typically 10-30) required for Thieve's Tools or Dexterity to pick the lock."
    )
    break_dc: Optional[int] = Field(
        default=None, 
        description="The Difficulty Class integer required for a Strength/Athletics check to physically break, shatter, or force the exit open."
    )
    secret_dc: Optional[int] = Field(
        default=None, 
        description="The passive or active Perception/Investigation DC required to locate this exit if is_discovered is set to False."
    )
    description: str = Field(
        description="A concise flavor description detailing what the door/egress looks like (e.g., 'A reinforced iron door bound with rusted banding.'). Passed to the Narrator."
    )

class NavigationGrid(BaseModel):
    map_layer: str = Field(
        description="The overarching localized reference region or sub-map layout name (e.g., 'Phandalin Overworld', 'Wave Echo Cave Floor 1')."
    )
    exits: List[ExitVector] = Field(
        default_factory=list, 
        description="A complete matrix of all explicit structural boundaries leading out of this node into adjacent spaces."
    )

# ==========================================
# 2. SENSORY, ENVIRONMENT & META SUB-MODELS
# ==========================================

class SensoryProfile(BaseModel):
    visual_clue: Optional[str] = Field(
        default=None, 
        description="Distinctive immediate visual characteristics noticed upon entering the room (e.g., 'Flickering green bioluminescent moss covering the pillars')."
    )
    olfactory_clue: Optional[str] = Field(
        default=None, 
        description="Smells, scents, or atmospheric air traits that give clues about the environment (e.g., 'The pungent aroma of wet dog and old copper blood')."
    )
    ambient_sound: Optional[str] = Field(
        default=None, 
        description="Acoustic features or underlying background noises present in the space (e.g., 'The distant, steady dripping of water echoing from the dark')."
    )
    thermal_clue: Optional[str] = Field(
        default=None, 
        description="Temperature anomalies or localized environmental thermal traits (e.g., 'A sudden chill that causes breath to fog up')."
    )

class EnvironmentProfile(BaseModel):
    lighting: str = Field(
        default="DIM_LIGHT", 
        description="The mechanical light level classification of the node. Must strictly evaluate to one: [DARKNESS, DIM_LIGHT, BRIGHT_LIGHT]."
    )
    resting_safety: str = Field(
        default="UNSAFE_DANGEROUS", 
        description="The rule enforcement status for player rests. Must strictly evaluate to one: [SAFE_REST_HAVEN, UNSAFE_DANGEROUS]."
    )
    dimensions: Optional[str] = Field(
        default=None, 
        description="The physical structure bounds or rough geometry of the space (e.g., 'A 30-foot circular domed burial crypt', 'An expansive open canyon')."
    )

class NodeMetadata(BaseModel):
    explicit_props: List[str] = Field(
        default_factory=list, 
        description="A collection of mundane, physical, non-magical furniture or architectural structures explicitly declared in the module text (e.g., ['burlap sacks', 'wooden bar stools', 'hearth fire'])."
    )
    sandbox_prop_tags: List[str] = Field(
        default_factory=list, 
        description="A list of 3-6 thematic, categorical environmental keywords used by the Python engine to evaluate if a player-invented prop is allowed to exist (e.g., ['scholarly', 'dusty', 'arcane', 'parchment'])."
    )
    procedural_traversal_allowed: bool = Field(
        default=True, 
        description="The structural sandbox toggle. If True, the engine allows players to use theater-of-the-mind to invent unlisted logical exits (like windows or pipes) using room tags."
    )
    room_states: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Dynamic runtime key-value ledger tracking environmental mutations across sessions (e.g., {'lever_pulled': True, 'sconces_lit': False}). Initialize as empty."
    )
    behavior_triggers: List[Dict[str, Any]] = Field(
        default_factory=list, 
        description="A matrix of scripted core engine conditional event hooks. Evaluates state metrics to fire backend engine action payloads (e.g., triggering traps or spawning reinforcements)."
    )

# ==========================================
# 3. MECHANICAL REFERENCE SUB-MODELS
# ==========================================

class EncounterReference(BaseModel):
    creature_id: str = Field(
        description="The normalized snake_case string ID referencing a universal decoupled monster manual entry (e.g., 'goblin', 'bugbear_chieftain')."
    )
    quantity: int = Field(
        description="The explicit baseline integer count of how many units of this specific monster inhabit the room by default."
    )

class LootTable(BaseModel):
    items: List[str] = Field(
        default_factory=list, 
        description="A collection of static unique item_ids, specific loot names, or gear keys contained within containers or on bodies in the node."
    )
    gold_pool: Optional[str] = Field(
        default=None, 
        description="The currency expression string representing available coinage or valuables, explicitly formatted in dice notation or standard integers (e.g., '2d6 * 10', '150')."
    )

# ==========================================
# 4. THE CORE BEANIE DOCUMENT
# ==========================================

class Node(Document):
    adventure_id: Annotated[str, Indexed()] = Field(
        description="The structural grouping ID anchoring this node to a specific campaign book, setting, or module (e.g., 'lost_mine_of_phandelver'). Used for compound index resolution."
    )
    node_id: str = Field(
        description="The explicit localized identification string for this specific node block, structured uniformly in snake_case (e.g., 'cragmaw_hideout_lvl1_room_04')."
    )
    parent_node_id: Optional[str] = Field(
        default=None, 
        description="A relational pointer up to a broader macro-node or structural cluster, allowing macro/micro sub-graph associations (e.g., an interior room points up to a city overworld)."
    )
    node_type: str = Field(
        default="INTERIOR_ROOM", 
        description="The classification scale of the geographical boundary. Must evaluate exactly to one: [CITY_OVERWORLD, REGIONAL_DISTRICT, BUILDING_POI, INTERIOR_ROOM]."
    )
    title: str = Field(
        description="The user-facing clean title or display name of the area shown to the players in Discord embeds (e.g., 'The Redbrand Hideout Cellar')."
    )
    
    navigation: NavigationGrid = Field(
        description="The topographical vector layout containing map layer configurations and verified path connections leading to other node documents."
    )
    environment: EnvironmentProfile = Field(
        description="The physical profiles regulating hard gameplay engine properties like lighting levels, layout constraints, and short/long resting parameters."
    )
    sensory_profile: SensoryProfile = Field(
        description="The atmospheric sensory data (sight, smell, hearing, touch) isolated during extraction and fed directly to the Narrator prompt framework."
    )
    node_metadata: NodeMetadata = Field(
        description="The core processing intelligence housing the Prop Sandbox data array, active environmental status states, and dynamic trigger logic hooks."
    )
    
    encounters: List[EncounterReference] = Field(
        default_factory=list, 
        description="The list of typed creature templates and quantities standing ready to engage the party upon room initiation."
    )
    treasure: LootTable = Field(
        default_factory=LootTable, 
        description="The structural ledger mapping out dropped currency parameters, equipment tables, or lockbox drop items."
    )
    interactables: List[Dict[str, Any]] = Field(
        default_factory=list, 
        description="Detailed schemas for custom unique puzzle blocks, explicit hidden trap triggers, or skill obstacles present in the geometry."
    )
    npc_profiles: List[Dict[str, Any]] = Field(
        default_factory=list, 
        description="Isolated named NPCs detailed in this area, including their primary behavioral goals and conversation node paths."
    )
    
    story_hooks: List[str] = Field(
        default_factory=list, 
        description="A collection of extracted story progression hooks, quest flags, or player updates associated with this specific location block."
    )
    campaign_lore: List[str] = Field(
        default_factory=list, 
        description="Historical information, world background data, or secret legends discovered when investigating or identifying this location."
    )
    
    llm_contexts: Dict[str, str] = Field(
        default_factory=dict, 
        description="The core markdown contextual storage dump. Contains a 'baseline_narration' key holding the unaltered, raw descriptive prose parsed out of the module text to act as the primary prompt source for the Narrator."
    )
    
    class Settings:
        name = "world_nodes"
        # Compound unique index enforces node_id uniqueness scoped purely inside that specific adventure, preventing collision errors across separate modules.
        indexes = [
            [
                ("adventure_id", 1),
                ("node_id", 1)
            ]
        ]