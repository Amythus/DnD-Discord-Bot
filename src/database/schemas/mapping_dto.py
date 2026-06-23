from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Any, Optional

class ExecutionEffectDTO(BaseModel):
    """
    Explicit schema matching the structural keys required by the 
    downstream execution engines to apply state updates.
    """
    effect_target: str = Field(
        description="The target variable or state engine dot-notation path to adjust (e.g., 'global_state.threat_level')."
    )
    set_value: Any = Field(
        description="The value, literal value string, or boolean flag applied directly to the designated target path."
    )

class GlobalBehaviorTriggerDTO(BaseModel):
    """
    Captures adventure-wide conditional scripts that override localized room states.
    """
    global_trigger_id: str = Field(description="Unique snake_case identifier for this global rule scenario.")
    conditions: List[str] = Field(description="List of tracking flag keys required to evaluate this override loop.")
    execution_effects: List[ExecutionEffectDTO] = Field(
        default_factory=list,
        description="Explicit structured sequence detailing property modifications applied across the state map."
    )

class MapEdgeDTO(BaseModel):
    """
    Shallow routing edge discovered during the macro map pass.
    """
    direction: str = Field(description="The relative direction or navigation vector (e.g., 'north', 'enter').")
    rough_target_description: str = Field(description="The plain-text destination phrasing parsed from prose.")
    inferred_target_node_id: Optional[str] = Field(
        None, description="The matching destination snake_case ID from the master index registry map."
    )

class NodeDiscoveryItem(BaseModel):
    """
    Temporary pipeline model capturing localized text slices from the raw markdown.
    """
    node_id: str = Field(description="Unique snake_case identifier for the location.")
    title: str = Field(description="Display name of the room or area.")
    raw_text_segment: str = Field(description="The exact raw text slice detailing this node.")

class AdventureMapDTO(BaseModel):
    """
    Phase 1 Map Pass schema used to discover macro configurations and 
    map layout boundaries without generating deep nested objects.
    """
    adventure_id: str = Field(description="Unique snake_case campaign grouping token.")
    module_name: str = Field(description="Clean display title for Discord dropdown configurations.")
    initiator_prompt: str = Field(description="Systemic instruction used to frame the environmental theme for the AI router.")
    story_hook: str = Field(description="Player-facing narrative introduction blurb printed to the Discord channel on game start.")
    
    default_npc_dispositions: Dict[str, str] = Field(default_factory=dict)
    initial_story_flags: Dict[str, bool] = Field(default_factory=dict)
    master_quest_registry: List[Dict[str, Any]] = Field(default_factory=list)
    global_behavior_triggers: List[GlobalBehaviorTriggerDTO] = Field(
        default_factory=list, 
        description="Adventure-wide interaction scripts collected globally during Pass 1."
    )
    
    node_registry: List[str] = Field(default_factory=list, description="Flat list of all valid snake_case node IDs.")
    discovered_nodes: List[NodeDiscoveryItem] = Field(description="The list of mapped segments found in the source document.")
    
    model_config = ConfigDict(
        extra='forbid',
        json_schema_extra={
            "example": {
                "adventure_id": "burnock_mill",
                "module_name": "The Mystery of Burnock Mill",
                "initiator_prompt": "An atmospheric, gritty adventure taking place in a rain-slicked valley topology...",
                "story_hook": "The party arrives at the muddy bank of the Burnock River, finding an old mill looming in the fog...",
                "default_npc_dispositions": {
                    "baron_uthrak_forces": "HOSTILE"
                },
                "initial_story_flags": {
                    "valley_on_high_alert": False
                },
                "global_behavior_triggers": [
                    {
                        "global_trigger_id": "uthrak_bounty_alert",
                        "conditions": ["party_kills_bridge_bandits == true"],
                        "execution_effects": [
                            {
                                "effect_target": "global_state.threat_level",
                                "set_value": "HIGH"
                            }
                        ]
                    }
                ],
                "node_registry": ["truss_bridge_u1"],
                "discovered_nodes": [
                    {
                        "node_id": "truss_bridge_u1",
                        "title": "U1. Truss Bridge",
                        "raw_text_segment": "### U1. Truss Bridge\nThis bridge over the Burnock River has..."
                    }
                ]
            }
        }
    )