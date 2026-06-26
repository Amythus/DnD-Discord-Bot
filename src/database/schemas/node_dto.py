from pydantic import BaseModel, Field, ConfigDict
from database.schemas.node_mechanical_dto import NodeMechanicalDTO
from database.schemas.node_narrative_dto import NodeNarrativeDTO
from database.models.campaign.adventure_node import NodeType
from typing import Optional, List, Dict, Any

class NodeDTO(BaseModel):
    # Core Identification
    adventure_id: str
    node_id: str
    parent_node_id: Optional[str] = None
    node_type: NodeType
    title: str
    
    # Aggregated from Mechanical/Narrative DTOs
    navigation: Any # NavigationGrid
    environment: Any # EnvironmentProfile
    sensory_profile: Any # SensoryProfile
    
    encounters: List[Any] = [] # List[EncounterReference]
    npc_profiles: List[Any] = [] # List[NPCProfile]
    interactables: List[Any] = [] # List[LocalInteractable]
    
    spatial_triggers: List[Any] = [] # List[SpatialTrigger]
    environmental_traps: List[Any] = [] # List[EnvironmentalTrap]
    timed_events: List[Any] = [] # List[TimedEvent]
    
    story_hooks: List[str] = []
    quests: List[Any] = [] # List[LocalQuestHook]
    campaign_lore: List[str] = []
    treasure: Any # LocalTreasure
    
    node_metadata: Any # NodeMetadata
    llm_contexts: Any # LLMContexts

    model_config = ConfigDict(extra='forbid', use_enum_values=True)