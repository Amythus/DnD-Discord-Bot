from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Any
from database.schemas.node_dto import NodeDTO 

class AdventureDTO(BaseModel):
    """
    The finalized, fully-hydrated campaign data structure consumed 
    by the core game engine.
    """
    adventure_id: str = Field(description="Unique snake_case campaign grouping token.")
    module_name: str = Field(description="Clean display title for Discord dropdown configurations.")
    initiator_prompt: str = Field(description="Cinematic introductory hook text.")
    
    default_npc_dispositions: Dict[str, str] = Field(default_factory=dict)
    initial_story_flags: Dict[str, bool] = Field(default_factory=dict)
    master_quest_registry: List[Dict[str, Any]] = Field(default_factory=list)
    
    nodes: List[NodeDTO] = Field(description="The complete array of flat campaign locations.")

    model_config = ConfigDict(
        extra='forbid',
        json_schema_extra={
            "example": {
                "adventure_id": "lost_mine_of_phandelver",
                "module_name": "Lost Mine of Phandelver (Chapter 1)",
                "initiator_prompt": "The rugged hills of the Sword Coast look peaceful, but danger lurks behind every crag...",
                "default_npc_dispositions": {
                    "gundren_rockseeker": "FRIENDLY"
                },
                "initial_story_flags": {
                    "goblin_ambush_triggered": False
                },
                "master_quest_registry": [
                    {"quest_id": "deliver_provisions", "title": "Deliver Gundren's Supplies", "is_essential": True}
                ],
                "nodes": []  
            }
        }
    )