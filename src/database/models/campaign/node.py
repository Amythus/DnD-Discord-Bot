from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from beanie import Document, Indexed

# =====================================================================
# 1. PASS 1 SKELETON: TOPOLOGICAL FIELDS
# =====================================================================

class NodeExit(BaseModel):
    """Maps deterministic navigation pathways for Python out-of-band tracking."""
    direction: str = Field(
        ..., 
        description="The directional command keyword vector (e.g., 'north', 'south', 'down', 'secret_door')."
    )
    target_node_id: str = Field(
        ..., 
        description="The unique snake_case identification string of the target destination node."
    )


class TopologySkeleton(BaseModel):
    """Captures the absolute structural map layout derived during Pass 1 processing."""
    exits: List[NodeExit] = Field(
        default_factory=list, 
        description="List of valid topological movement corridors extending from this node."
    )


# =====================================================================
# 2. PASS 2 HYDRATION: MECHANICAL ENTITIES (SEMANTICALLY OPTIMIZED)
# =====================================================================

class CombatantEntity(BaseModel):
    """
    Unified Pass 2 Entity: Holds rigid headcount metrics alongside 
    flexible narrative placement context for prompt locality optimization.
    """
    entity_template_key: str = Field(
        ..., 
        description="Rigid snake_case template key referencing the monster/humanoid catalog (e.g., 'goblin_scout')."
    )
    quantity: int = Field(
        ..., 
        description="Rigid headcount used by the backend initialization engine to spawn active tokens."
    )
    narrative_position: str = Field(
        ..., 
        description="Narrative context of where they are or what they are doing (e.g., 'Sleeping around the fire pit')."
    )


class InteractionObstacle(BaseModel):
    """A narrative challenge gating access or items, interpreted freely using cached rulebooks."""
    description: str = Field(
        ..., 
        description="Verbatim physical appearance and placement anchor in the room (e.g., 'A reinforced iron gate blocking the northern archway')."
    )
    resolution_criteria: str = Field(
        ...,
        description=(
            "Freeform prose describing successful resolution vectors. Trust the Adjudicator to evaluate "
            "skill proficiencies, tool alternate scores, or magical spell counters natively "
            "(e.g., 'Requires an Athletics check to pry open, or picking via Thieves\' Tools. "
            "Spells like Knock bypass this automatically. Characters with a Soldier background roll with advantage.')."
        )
    )
    dc_baseline: int = Field(
        ..., 
        description="The default difficulty class value. The Adjudicator may adjust this up/down based on player tools or spells."
    )
    failure_consequences: Optional[str] = Field(
        default=None,
        description=(
            "Prose instructions detailing what occurs on failure. Rely on cached rulebook state rules "
            "(e.g., 'Tripping the mechanism forces a Dexterity saving throw. Failure inflicts 2d6 piercing damage "
            "from wall darts and alerts nearby creatures. Success halves the damage.')."
        )
    )
    engine_callback_key: Optional[str] = Field(
        default=None,
        description="Optional strict snake_case hook used by backend Python scripts to pause queues or apply persistent world states."
    )


class LootItem(BaseModel):
    """Textual reward array. Blends strict financial valuation parameters with prose discovery rules."""
    description: str = Field(
        ..., 
        description="Verbatim naming or text detailing the reward (e.g., '+1 Longsword', 'Gundren\'s journal')."
    )
    gp_value: int = Field(
        default=0,
        description="Rigid integer representation of base gold piece value for shopping/spell-component cost compliance evaluation."
    )
    value_notes: Optional[str] = Field(
        default=None,
        description="Narrative context regarding worth or appraisal subtleties (e.g., 'worthless to merchants but priceless to local academies')."
    )
    loot_source_or_location: str = Field(
        ..., 
        description="Verbatim detail of where it is found or who holds it (e.g., 'Tucked securely into the goblin chieftain\'s left boot')."
    )
    discovery_criteria: str = Field(
        default="Completely visible upon entering the area context.",
        description=(
            "Prose guiding how the Adjudicator screens player observation actions "
            "(e.g., 'Requires searching the ash pile with a successful Investigation check. "
            "Passive perception will not notice it. Characters using Detect Magic perceive a faint transmutation aura.')."
        )
    )
    bypass_obstacle: Optional[InteractionObstacle] = Field(
        default=None,
        description="Optional physical barrier or stealth challenge guarding the item once its location is discovered."
    )


class LogicTrigger(BaseModel):
    """Deterministic validation hooks checked by Python middleware and evaluated semantically by the Adjudicator."""
    adjudicator_narrative_condition: str = Field(
        ...,
        description=(
            "AI-interpretable plain-text scenario leveraging context-cached rulebooks "
            "(e.g., 'Triggers instantly if players cross the center stream without executing a successful "
            "Group Stealth check vs the Goblin scouts\' passive perception, OR if light sources expose them.')."
        )
    )
    engine_callback_key: str = Field(
        ...,
        description="Strict snake_case hook used by backend Python scripts to pause queues or apply mutations (e.g., 'trip_wire_collapse')."
    )


class MechanicalEntities(BaseModel):
    """Interactive assets and encounter tracking groups parsed out during Pass 2."""
    combatants: List[CombatantEntity] = Field(
        default_factory=list, 
        description="Highly rigid array of monsters, hostile humanoids, and active NPCs ready for token generation."
    )
    loot_array: List[LootItem] = Field(
        default_factory=list, 
        description="Flexible textual array representing local rewards, valuables, and container layers."
    )
    standalone_obstacles: List[InteractionObstacle] = Field(
        default_factory=list,
        description="Physical challenges or interactions unbound to treasure (e.g., stuck doors, heavy pull levers, stealth guards)."
    )
    triggers: List[LogicTrigger] = Field(
        default_factory=list, 
        description="Environmental, spatial, or behavioral logic interrupts evaluated prior to text adjudication."
    )


# =====================================================================
# 3. PASS 3 HYDRATION: NARRATIVE & ATMOSPHERIC ENTITIES
# =====================================================================

class SensoryProfile(BaseModel):
    """Multi-sensory contextual profile breakdown matching Pass 3 structural ingestion blocks."""
    sight: str = Field(default="", description="Visual description elements framing the location.")
    sound: str = Field(default="", description="Auditory profiles or subtle echoes present in the space.")
    smell: str = Field(default="", description="Olfactory details detailing the atmosphere context.")
    temperature: str = Field(default="ambient", description="Thermal climate attributes of the local coordinate area.")


class LoreContext(BaseModel):
    """Detailed room background context passed directly down to the DM Assistant prompt context."""
    spatial_dimensions: str = Field(
        ..., 
        description="Physical layout dimensions or structural configuration details (e.g., 'A 20x30ft vaulted vault')."
    )
    sensory_profile: SensoryProfile = Field(
        default_factory=SensoryProfile, 
        description="Broken-out multi-sensory variables."
    )
    narrative_history: Optional[str] = Field(
        default=None, 
        description="Static historical background lore that has no direct mechanical bearing on the simulation engine."
    )


class NarrativeAtmosphere(BaseModel):
    """The bulk token weight components designed to pack directly into Gemini Context Caching layers."""
    title: str = Field(
        ..., 
        description="User-facing descriptive name for the room displayed directly onto the client/Discord UI."
    )
    description: str = Field(
        ..., 
        description="Verbatim markdown flavor description text parsed down to frame the scene for the active player."
    )
    lore: LoreContext = Field(
        ..., 
        description="Sub-document containing structural backdrop and sensory constraints."
    )
    sandbox_prop_tags: List[str] = Field(
        default_factory=list, 
        description=(
            "Inferred environmental objects not explicitly written in the module text, but logically "
            "present based on room context for sandboxed theatre-of-the-mind interactions (e.g., ['wooden_stools', 'chandeliers'] for taverns)."
        )
    )


# =====================================================================
# ROOT DATABASE DOCUMENT: IMMUTABLE MAP BLUEPRINT
# =====================================================================

class GameNode(Document):
    """
    The finalized compilation target inside MongoDB representing an immutable map layout.
    Free from session-specific tracking, ensuring flawless scalability and caching.
    """
    adventure_id: Indexed(str) = Field(
        ..., 
        description="Groups structural room nodes cleanly under a macro-parent campaign blueprint identifier."
    )
    node_id: Indexed(str) = Field(
        ..., 
        description="Unique snake_case identifier within this specific adventure's Node Matrix."
    )
    parent_id: Optional[str] = Field(
        default=None, 
        description="Optional recursive indicator pointing up to a regional, sub-level, or area layout container."
    )
    
    # Structural Pipeline Steps
    topology: TopologySkeleton = Field(
        ..., 
        description="Data bound to Pass 1 skeleton extraction rules."
    )
    mechanics: MechanicalEntities = Field(
        default_factory=MechanicalEntities, 
        description="Data bound to Pass 2 interaction and encounter asset insertion rules."
    )
    narrative: NarrativeAtmosphere = Field(
        ..., 
        description="Data bound to Pass 3 text-heavy description and caching layout rules."
    )

    class Settings:
        name = "game_nodes"
        indexes = [
            "adventure_id",
            "node_id",
            ["adventure_id", "node_id"] 
        ]