from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Any
from database.schemas.node_dto import NodeDTO 

class AdventureDTO(BaseModel):
    """
    The strict Pass 1 output schema capturing both flat spatial maps 
    and macro-level campaign constraints simultaneously.
    """
    adventure_id: str = Field(description="Unique snake_case campaign grouping token.")
    module_name: str = Field(description="Clean display title for Discord dropdown configurations.")
    initiator_prompt: str = Field(description="Cinematic introductory hook text.")
    
    default_npc_dispositions: Dict[str, str] = Field(default_factory=dict)
    initial_story_flags: Dict[str, bool] = Field(default_factory=dict)
    master_quest_registry: List[Dict[str, Any]] = Field(default_factory=list)
    
    # The flat adjacency list rows
    nodes: List[NodeDTO] = Field(description="The full array of flat campaign locations.")

    model_config = ConfigDict(extra='forbid')