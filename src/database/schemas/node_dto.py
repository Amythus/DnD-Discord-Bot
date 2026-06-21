from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Any, Optional
from database.models.spatial.node import (
    NavigationGrid, 
    EnvironmentProfile, 
    SensoryProfile, 
    NodeMetadata, 
    EncounterReference, 
    LootTable, 
    QuestHook
)

class NodeDTO(BaseModel):
    """
    Data Transfer Object representing a node in the game world.
    Used for API communication and state serialization.
    """
    adventure_id: str = Field(description="The structural grouping ID anchoring this node to a specific campaign book.")
    node_id: str = Field(description="The explicit localized identification string for this specific node block, structured uniformly in snake_case.")
    parent_node_id: Optional[str] = Field(default=None, description="Relational pointer up to a broader macro-node, regional layout, or Campaign Root anchor.")
    node_type: str = Field(description="Must evaluate exactly to one: [CAMPAIGN_ROOT, CITY_OVERWORLD, REGIONAL_DISTRICT, BUILDING_POI, INTERIOR_ROOM].")
    title: str = Field(description="The user-facing clean title or display name shown to the players in Discord embeds.")
    
    navigation: NavigationGrid = Field(description="The vector layout containing map layer configurations and verified path connections.")
    environment: EnvironmentProfile = Field(description="The physical profiles regulating hard gameplay engine rules like lighting and safety.")
    sensory_profile: SensoryProfile = Field(description="Atmospheric sensory data isolated during extraction and fed directly to the Narrator.")
    node_metadata: NodeMetadata = Field(description="The processing intelligence housing sandbox prop parameters, active mutations, and logic triggers.")
    
    encounters: List[EncounterReference] = Field(default_factory=list, description="List of creature encounters defined for this node.")
    treasure: LootTable = Field(default_factory=LootTable, description="Definition of loot and currency found within the node.")
    interactables: List[Dict[str, Any]] = Field(default_factory=list, description="Custom unique puzzles, locked chest mechanics, or hidden trap rules.")
    npc_profiles: List[Dict[str, Any]] = Field(default_factory=list, description="Named NPCs found in this area, including behavioral goals and dialog roots.")
    
    # quest_registry: List[QuestHook] = Field(default_factory=list, description="Only populated on the CAMPAIGN_ROOT node. Master array tracking all game quests.")
    story_hooks: List[str] = Field(default_factory=list, description="Extracted localized plot hooks, specific rumors, or quest updates tied to this space.")
    campaign_lore: List[str] = Field(default_factory=list, description="Historical world background elements, secret legends, or local context lore records.")
    
    llm_contexts: Dict[str, str] = Field(default_factory=dict, description="Holds a 'baseline_narration' key containing the unaltered descriptive background prose.")

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
        json_schema_extra = {
            "example": {
                "adventure_id": "lost_mine_of_phandelver",
                "node_id": "cragmaw_hideout_cave_entrance",
                "parent_node_id": "neverwinter_woods_region",
                "node_type": "INTERIOR_ROOM",
                "title": "Cave Mouth",
                "navigation": {
                    "map_layer": "Cragmaw Hideout Lower Level",
                    "exits": [
                        {
                            "direction": "east",
                            "type": "NATURAL_FISSURE",
                            "target_node_id": "cragmaw_hideout_kennels",
                            "is_open": True,
                            "is_locked": False,
                            "is_discovered": True,
                            "description": "A dark, narrow opening leading into the rock face where a low snarling echoes."
                        },
                        {
                            "direction": "INTERACTIVE",
                            "interaction_verb": "climb_rubble",
                            "type": "STONE_SLAB",
                            "target_node_id": "cragmaw_hideout_overlook",
                            "is_open": True,
                            "is_locked": False,
                            "is_discovered": False,
                            "secret_dc": 14,
                            "description": "A hidden set of crude handholds stepping up a steep scree slope behind a screen of briars."
                        }
                    ]
                },
                "environment": {
                    "lighting": "DARKNESS",
                    "resting_safety": "UNSAFE_DANGEROUS",
                    "dimensions": "A ragged 40-foot opening carved into the base of a cliffside."
                },
                "sensory_profile": {
                    "visual_clue": "A shallow stream trickles out of the mouth, pooling along muddy tracks.",
                    "olfactory_clue": "The damp, stagnant scent of rotting vegetation and wet fur fills the air.",
                    "ambient_sound": "The rhythmic sound of rushing water deeper in the darkness.",
                    "thermal_clue": "A damp, cool draft spills outward from the cavern cavern floor."
                },
                "node_metadata": {
                    "explicit_props": ["muddy tracks", "briar screen", "shallow stream"],
                    "sandbox_prop_tags": ["stone", "cave", "wild", "water"],
                    "procedural_traversal_allowed": True,
                    "parent_alert_flags": {
                        "hideout_on_alert": False
                    },
                    "room_states": {
                        "stream_dammed": False,
                        "guard_goblins_alerted": False
                    },
                    "behavior_triggers": [
                        {
                            "trigger_condition": "room_states.guard_goblins_alerted == true",
                            "action_payload": {
                                "mutate_target": "node_metadata.parent_alert_flags.hideout_on_alert",
                                "set_value": True
                            }
                        }
                    ]
                },
                "encounters": [
                    {
                        "creature_id": "goblin",
                        "quantity": 2,
                        "is_procedural_table": False
                    }
                ],
                "treasure": {
                    "items": ["rusted_scimitar"],
                    "gold_pool": "2d4"
                },
                "interactables": [],
                "npc_profiles": [],
                "story_hooks": ["Found clues of Gundren Rockseeker's capture."],
                "campaign_lore": ["This cave has been utilized by the Cragmaw goblin tribe for the past three seasons."],
                "llm_contexts": {
                    "baseline_narration": "Following the goblin trail, you arrive at a hillside where a shallow stream flows out of a dark cave mouth. The opening is masked by dense briars..."
                }
            }
        }
    )