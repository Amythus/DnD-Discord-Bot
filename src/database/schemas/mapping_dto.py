from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Any

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
    initiator_prompt: str = Field(description="Cinematic introductory hook text.")
    
    default_npc_dispositions: Dict[str, str] = Field(default_factory=dict)
    initial_story_flags: Dict[str, bool] = Field(default_factory=dict)
    master_quest_registry: List[Dict[str, Any]] = Field(default_factory=list)
    
    node_registry: List[str] = Field(default_factory=list, description="Flat list of all valid snake_case node IDs.")
    discovered_nodes: List[NodeDiscoveryItem] = Field(description="The list of mapped segments found in the source document.")
    
    model_config = ConfigDict(
        extra='forbid',
        json_schema_extra={
            "example": {
                "adventure_id": "lost_mine_of_phandelver",
                "module_name": "Lost Mine of Phandelver",
                "initiator_prompt": "The rugged hills look peaceful...",
                "node_registry": ["area_01_goblin_ambush"],
                "discovered_nodes": [
                    {
                        "node_id": "area_01_goblin_ambush",
                        "title": "Area 1: Goblin Ambush",
                        "raw_text_segment": "### Area 1: Goblin Ambush\nTwo dead horses block the path..."
                    }
                ]
            }
        }
    )