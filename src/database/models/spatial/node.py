from enum import Enum
from beanie import Document, Indexed
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Annotated, Literal

# ==========================================
# 1. ENUMS & STRUCTURAL TAXONOMY
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

ValidDirection = Literal["north", "south", "east", "west", "northeast", "northwest", "southeast", "southwest", "up", "down", "enter", "exit", "INTERACTIVE"]

class QuestStatus(str, Enum):
    LOCKED = "LOCKED"
    AVAILABLE = "AVAILABLE"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"

# ==========================================
# 2. SUB-MODELS FOR TYPED REFERENCES
# ==========================================

class ExitVector(BaseModel):
    direction: ValidDirection = Field(
        description="The structural compass heading, verticality indicator, or spatial vector representing the path."
    )
    interaction_verb: Optional[str] = Field(
        default=None, 
        description="Required ONLY if direction is 'INTERACTIVE'. The command word or interactive item verb that triggers travel (e.g., 'shake_ivory_shaker', 'step_into_scroll')."
    )
    type: ExitType = Field(
        description="The physical or magical taxonomy classification of this specific traversal boundary obstacle."
    )
    target_node_id: str = Field(
        description="The deterministic snake_case ID of the destination world_node this edge connects to (e.g., 'lost_mine_of_phandelver_lvl1_room_02')."
    )
    is_open: bool = Field(default=True, description="True if unobstructed, False if blocked.")
    is_locked: bool = Field(default=False, description="True if it requires a mechanical key, magic word, or active lockpicking check.")
    is_discovered: bool = Field(default=True, description="False if this is a hidden secret door requiring a skill check to find.")
    lock_dc: Optional[int] = Field(default=None, description="The standard D&D Difficulty Class integer (10-30) required to pick the lock.")
    break_dc: Optional[int] = Field(default=None, description="The Difficulty Class integer required for a Strength/Athletics check to physically smash it open.")
    secret_dc: Optional[int] = Field(default=None, description="The Perception/Investigation DC required to locate this path if is_discovered is set to False.")
    description: str = Field(
        description="A concise flavor description detailing what the egress looks like (e.g., 'A reinforced iron door bound with rusted banding.'). Passed to the Narrator."
    )

class NavigationGrid(BaseModel):
    map_layer: str = Field(
        description="The overarching localized reference region or sub-map layout name (e.g., 'Sword Coast Map', 'Phandalin Town Square', 'Wave Echo Cave Floor 1')."
    )
    exits: List[ExitVector] = Field(
        default_factory=list, 
        description="A complete matrix of all explicit structural boundaries leading out of this node into adjacent spaces."
    )

class SensoryProfile(BaseModel):
    visual_clue: Optional[str] = Field(default=None, description="Immediate visual traits noticed upon entry.")
    olfactory_clue: Optional[str] = Field(default=None, description="Smells, scents, or atmospheric air traits.")
    ambient_sound: Optional[str] = Field(default=None, description="Acoustic features or underlying background noises.")
    thermal_clue: Optional[str] = Field(default=None, description="Temperature anomalies or localized environmental traits.")

class EnvironmentProfile(BaseModel):
    lighting: str = Field(default="DIM_LIGHT", description="Must evaluate strictly to one: [DARKNESS, DIM_LIGHT, BRIGHT_LIGHT].")
    resting_safety: str = Field(default="UNSAFE_DANGEROUS", description="Must evaluate strictly to one: [SAFE_REST_HAVEN, UNSAFE_DANGEROUS].")
    dimensions: Optional[str] = Field(default=None, description="The physical structure bounds or rough geometry (e.g., 'A 30-foot circular crypt').")

class NodeMetadata(BaseModel):
    explicit_props: List[str] = Field(
        default_factory=list, 
        description="Mundane physical furniture or structural elements explicitly detailed in the text (e.g., ['wooden bar stools', 'hearth fire'])."
    )
    sandbox_prop_tags: List[str] = Field(
        default_factory=list, 
        description="A list of 3-6 thematic keywords used by the Python engine to validate player-invented theater-of-the-mind props (e.g., ['wooden', 'tavern', 'cluttered'])."
    )
    procedural_traversal_allowed: bool = Field(
        default=True, 
        description="If True, the engine allows players to creatively invent unlisted logical exits using sandbox tags."
    )
    room_states: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Dynamic runtime key-value ledger tracking environmental mutations across sessions (e.g., {'lever_pulled': True, 'sconces_lit': False})."
    )
    behavior_triggers: List[Dict[str, Any]] = Field(
        default_factory=list, 
        description="Automated scripted event hooks that evaluate metrics to trigger core engine action payloads."
    )

class EncounterReference(BaseModel):
    creature_id: str = Field(description="The normalized snake_case string ID referencing a universal decoupled monster manual entry.")
    quantity: int = Field(description="The explicit baseline integer count of how many units of this specific monster inhabit the room by default.")
    is_procedural_table: bool = Field(default=False, description="True if the quantity requires rolling on a random d20 or d% table.")
    table_roll_notation: Optional[str] = Field(default=None, description="The random roll expression or lookup key (e.g., '1d4 + 1' or 'phandalin_travel_encounters').")

class LootTable(BaseModel):
    items: List[str] = Field(default_factory=list, description="A collection of static unique item_ids or weapon gear keys inside chests or on bodies.")
    gold_pool: Optional[str] = Field(default=None, description="Currency reward string, explicitly formatted in dice notation or standard integers (e.g., '2d6 * 10', '150').")

class QuestHook(BaseModel):
    quest_id: str = Field(description="The snake_case unique tracker ID for the quest.")
    title: str = Field(description="The public title of the quest shown to the players.")
    giver: str = Field(description="The name of the entity or board providing the quest.")
    prerequisite_quest_ids: List[str] = Field(default_factory=list, description="List of quest_ids that must be completed before this quest unlocks.")
    reward_payload: Dict[str, Any] = Field(default_factory=dict, description="Mechanical reward schema (e.g., {'gp': 50, 'items': ['boots_of_elvenkind']}).")
    description: str = Field(description="The verbatim rumor or job posting text shown on the quest log or message board.")

# ==========================================
# 3. THE CORE UNIVERSAL BEANIE DOCUMENT
# ==========================================

class Node(Document):
    adventure_id: Annotated[str, Indexed()] = Field(
        description="The structural grouping ID anchoring this node to a specific campaign book, setting, or module (e.g., 'dragon_of_icespire_peak')."
    )
    node_id: str = Field(
        description="The explicit localized identification string for this specific node block, structured uniformly in snake_case (e.g., 'phandalin_town_square')."
    )
    parent_node_id: Optional[str] = Field(
        default=None, 
        description="Relational pointer up to a broader macro-node, regional layout, or Campaign Root anchor, enabling hierarchical inheritance loops."
    )
    node_type: str = Field(
        default="INTERIOR_ROOM", 
        description="Must evaluate exactly to one: [CAMPAIGN_ROOT, CITY_OVERWORLD, REGIONAL_DISTRICT, BUILDING_POI, INTERIOR_ROOM]."
    )
    title: str = Field(description="The user-facing clean title or display name shown to the players in Discord embeds.")
    
    navigation: NavigationGrid = Field(description="The vector layout containing map layer configurations and verified path connections.")
    environment: EnvironmentProfile = Field(description="The physical profiles regulating hard gameplay engine rules like lighting and safety.")
    sensory_profile: SensoryProfile = Field(description="Atmospheric sensory data isolated during extraction and fed directly to the Narrator.")
    node_metadata: NodeMetadata = Field(description="The processing intelligence housing sandbox prop parameters, active mutations, and logic triggers.")
    
    encounters: List[EncounterReference] = Field(default_factory=list)
    treasure: LootTable = Field(default_factory=LootTable)
    interactables: List[Dict[str, Any]] = Field(default_factory=list, description="Custom unique puzzles, locked chest mechanics, or hidden trap rules.")
    npc_profiles: List[Dict[str, Any]] = Field(default_factory=list, description="Named NPCs found in this area, including behavioral goals and dialog roots.")
    
    # Global Campaign-Scale Tracking Vectors
    quest_registry: List[QuestHook] = Field(
        default_factory=list, 
        description="Only populated on the CAMPAIGN_ROOT node. Houses the master array tracking the status of all active, locked, and completed game quests."
    )
    story_hooks: List[str] = Field(default_factory=list, description="Extracted localized plot hooks, specific rumors, or quest updates tied to this space.")
    campaign_lore: List[str] = Field(default_factory=list, description="Historical world background elements, secret legends, or local context lore records.")
    
    llm_contexts: Dict[str, str] = Field(
        default_factory=dict, 
        description="Holds a 'baseline_narration' key containing the unaltered, highly descriptive background prose parsed out of the book to guide the Narrator."
    )
    
    class Settings:
        name = "world_nodes"
        indexes = [
            [
                ("adventure_id", 1),
                ("node_id", 1)
            ]
        ]