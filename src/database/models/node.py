from typing import List, Optional, Dict, Any
from beanie import Document, Indexed
from pydantic import BaseModel, Field

class BehaviorTrigger(BaseModel):
    trigger_type: str = Field(description="e.g., player_action, round_end, item_interaction, death_event")
    condition: str = Field(description="The functional evaluation condition (e.g., 'combat_round_counter == 2' or 'ordered_boiling_oil')")
    action_required: str = Field(description="The mechanical engine payload tag (e.g., 'spawn_reinforcements', 'set_flag', 'teleport_player')")
    instruction_to_narrator: str = Field(description="Verbatim script directives passed to the Narrator LLM when this block resolves.")

class NodeMetadata(BaseModel):
    # A fully fluid key-value state tracker initialized during ingestion or game startup
    room_states: Dict[str, Any] = Field(default_factory=dict)
    behavior_triggers: List[BehaviorTrigger] = Field(default_factory=list)

class Node(Document):
    node_id: Indexed(str, unique=True)
    parent_node_id: Optional[Indexed(str)] = None
    node_type: str = "INTERIOR_ROOM"
    title: str
    
    # STRUCTURAL ESSENTIALS
    navigation: Dict[str, Any] = Field(default_factory=dict) # Lean array of exits and open statuses
    environment: Dict[str, Any] = Field(default_factory=dict) # Dimensions, lighting, zones
    sensory_profile: Dict[str, Optional[str]] = Field(default_factory=dict)
    
    # YOUR NEW UNIVERSAL ENGINE CORE (Replaces all previous edge-case sub-classes)
    node_metadata: NodeMetadata
    
    # DECOUPLED INVENTORY & SPAWN REFERENCES
    encounters: List[Dict[str, Any]] = [] # Only tracks baseline ['creature_id', 'quantity']
    treasure: Dict[str, Any] = Field(default_factory=dict) # Simple item loot tables
    
    # SEMANTIC TEXT CONTAINERS
    llm_contexts: Dict[str, str] = Field(default_factory=dict)

    class Settings:
        name = "campaign_world_graph"
