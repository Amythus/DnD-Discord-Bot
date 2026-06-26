from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Any

class NodeDiscoveryItem(BaseModel):
    node_id: str
    title: str
    raw_text_segment: str

class AdventureMapDTO(BaseModel):
    adventure_id: str
    module_name: str
    initiator_prompt: str
    story_hook: str
    
    default_npc_dispositions: Dict[str, str] = Field(default_factory=dict)
    initial_story_flags: Dict[str, bool] = Field(default_factory=dict)
    node_registry: List[str]
    discovered_nodes: List[NodeDiscoveryItem]
    
    model_config = ConfigDict(extra='forbid')