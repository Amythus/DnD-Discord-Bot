from pydantic import BaseModel, Field, ConfigDict, field_validator
from database.models.spatial.node import (
    NodeType,
    NavigationGrid,
    EnvironmentProfile,
    SensoryProfile,
    EncounterReference,
    NPCProfile,
    LocalInteractable,
    SpatialTrigger,
    EnvironmentalTrap,
    TimedEvent,
    LocalQuestHook,
    LocalTreasure,
    NodeMetadata,
    LLMContexts
)
from typing import List, Optional, Any

class NodeDTO(BaseModel):
    """
    Decoupled Phase 2 Data Transfer Object mapping a single room text slice.
    Includes validation sanitization to resolve lowercase extraction anomalies.
    """
    adventure_id: str = Field(
        description="The parent project grouping token matching the Phase 1 map configuration (e.g., 'burnock_mill')."
    )
    node_id: str = Field(
        description="The structural identifier for this local entity, generated strictly in snake_case (e.g., 'truss_bridge_u1')."
    )
    parent_node_id: Optional[str] = Field(
        default=None, 
        description="Optional tracking string linking this zone to a macro layer index block."
    )
    node_type: NodeType = Field(
        description="The spatial typology tier representing this specific area's classification framework."
    )
    title: str = Field(
        description="The exact formal display heading parsed out of the markdown content header (e.g., 'U1. Truss Bridge')."
    )
    
    navigation: NavigationGrid = Field(
        description="The navigation grid containing exits, directions, lock validation metrics, and destination identifiers."
    )
    environment: EnvironmentProfile = Field(
        description="The baseline physics constraints managing visibility parameters and group recovery guidelines."
    )
    sensory_profile: SensoryProfile = Field(
        description="The sensory metadata describing visual landmarks, scents, thermal spikes, and audio textures."
    )
    
    encounters: List[EncounterReference] = Field(
        default_factory=list, 
        description="An array of localized enemy or trap creature templates that scale into action when combat loops execute."
    )
    npc_profiles: List[NPCProfile] = Field(
        default_factory=list, 
        description="A list of unique interactive actors, complete with custom agendas, names, and conversational attachments."
    )
    interactables: List[LocalInteractable] = Field(
        default_factory=list, 
        description="Physical architecture models or props placed here that support manual player manipulation."
    )
    
    spatial_triggers: List[SpatialTrigger] = Field(
        default_factory=list, 
        description="Reactive context handlers running systemic mutations instantly when room boundary thresholds are crossed."
    )
    environmental_traps: List[EnvironmentalTrap] = Field(
        default_factory=list, 
        description="Hidden dangers tracking explicit mechanical damage distributions, detection thresholds, and recovery methods."
    )
    timed_events: List[TimedEvent] = Field(
        default_factory=list, 
        description="Phased actions or environment updates processing continuously on distinct turn progression offsets."
    )
    
    story_hooks: List[str] = Field(
        default_factory=list, 
        description="Global narrative state changes or system declarations broadcasted when this environment layer is resolved."
    )
    quests: List[LocalQuestHook] = Field(
        default_factory=list, 
        description="Relational hooks that update or activate player ledger contracts within this zone."
    )
    campaign_lore: List[str] = Field(
        default_factory=list, 
        description="World history entries unlocked when characters run extensive search loops inside this area."
    )
    treasure: LocalTreasure = Field(
        default_factory=lambda: LocalTreasure(), 
        description="A structured loot asset detailing currency storage pools and unique item properties present on disk."
    )
    
    node_metadata: NodeMetadata = Field(
        description="Backend administrative indicators managing automated routing, physical props, and regional tracking states."
    )
    llm_contexts: LLMContexts = Field(
        description="Atmospheric reference copy serving as the generation baseline for player introduction modules."
    )

    @field_validator('node_type', mode='before')
    @classmethod
    def coerce_node_type_uppercase(cls, v: Any) -> Any:
        return v.upper() if isinstance(v, str) else v
    
    model_config = ConfigDict(
        extra='forbid',
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "adventure_id": "burnock_mill",
                "node_id": "truss_bridge_u1",
                "parent_node_id": None,
                "node_type": "BUILDING_POI",
                "title": "U1. Truss Bridge",
                "navigation": {
                    "map_layer": "Burnock River Region",
                    "exits": [
                        {
                            "direction": "enter",
                            "target_node_id": "burnock_mill_exterior",
                            "exit_type": "OPEN_THOROUGHFARE",
                            "description": "The path off the wooden planks directly reaches the nearby mill structure.",
                            "is_locked": False
                        }
                    ]
                },
                "environment": {
                    "lighting": "BRIGHT_LIGHT",
                    "resting_safety": "UNSAFE_DANGEROUS",
                    "dimensions": "Sturdy covered wood plank bridge measuring 10 feet wide spanning a fast river."
                },
                "sensory_profile": {
                    "visual_clue": "A covered wooden truss bridge spans the river; five figures sit casually on the roof framework.",
                    "ambient_sound": "The continuous rushing noise of a fast-moving river passing under the planks."
                },
                "encounters": [
                    {"creature_id": "flash_maggie_brawler", "quantity": 1},
                    {"creature_id": "gray_walter_storm_wizard", "quantity": 1},
                    {"creature_id": "apprentice_mage", "quantity": 3}
                ],
                "npc_profiles": [
                    {
                        "npc_id": "flash_maggie",
                        "name": "Flash Maggie",
                        "disposition": "HOSTILE",
                        "short_description": "A fierce human brawler serving as the toll bandit captain.",
                        "agenda": "Sarcastically demand a toll of half the party's total gold pool, attacking if refused.",
                        "dialog_root_id": "flash_maggie_toll_convo"
                    }
                ],
                "interactables": [
                    {
                        "interactable_id": "bridge_climbing_beams",
                        "name": "Scaffolding Hooks",
                        "description": "Sturdy hooks stick out of the beams on the bridge structure.",
                        "interaction_effect": "Allows any creature to freely climb to the roof scaffolding layer without making an ability check.",
                        "execution_effects": []
                    }
                ],
                "spatial_triggers": [
                    {
                        "trigger_id": "river_current_sweep",
                        "conditions": ["creature_starts_turn_in_river == true", "creature_has_swimming_speed == false"],
                        "execution_effects": [
                            {
                                "effect_target": "creature.position",
                                "set_value": "Must pass a DC 13 Strength save or be forced 5 feet west."
                            }
                        ]
                    }
                ],
                "environmental_traps": [
                    {
                        "trap_id": "burnock_river_hazard",
                        "name": "10-foot-deep Fast River Current",
                        "detection_dc": 10,
                        "disarm_mechanism": "Cannot be mechanically disarmed; a natural water hazard.",
                        "mechanical_effect": "Requires a DC 13 Strength save at turn start or forces a 5-foot slide west."
                    }
                ],
                "timed_events": [],
                "story_hooks": [
                    "Defeating the bandits yields a warning: 'You may have beaten us, but Baron Uthrak will have his revenge! No one crosses the baron and lives.'"
                ],
                "quests": [],
                "campaign_lore": [
                    "Baron Uthrak has hired mercenary muscle to extort regional thoroughly fares across the Burnock River basin."
                ],
                "treasure": {
                    "gold_pool": 120,
                    "items": [
                        {
                            "item_id": "signed_toll_receipts",
                            "name": "Signed Toll Receipts",
                            "description": "Receipts signed explicitly by Baron Uthrak detailing 600 gp of collected tolls over the past month."
                        }
                    ]
                },
                "node_metadata": {
                    "explicit_props": ["sturdy plank bridge", "climbing hooks", "deep river"],
                    "sandbox_prop_tags": ["bridge", "climbable", "water"],
                    "procedural_traversal_allowed": True,
                    "parent_alert_flags": {"mill_garrison_notified": False}
                },
                "llm_contexts": {
                    "baseline_narration": "A sturdy plank bridge arches across the rushing waters of the Burnock River, completely covered by a framework of heavy wooden beams..."
                }
            }
        }
    )