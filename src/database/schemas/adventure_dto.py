from typing import List, Dict, Optional
from pydantic import BaseModel, Field

class NodeEncounterDTO(BaseModel):
    """Strict schema for pre-seeding monsters inside a room."""
    monster_name: str = Field(..., description="Name of the monster or NPC matching the bestiary database.")
    quantity: int = Field(..., description="Number of these specific entities present in the node.")
    
    model_config = {"extra": "forbid"}

class NodeDTO(BaseModel):
    """
    A single, flat location node extracted from the adventure markdown.
    Designed for immediate upsert into the Node Matrix Adjacency List.
    """
    node_id: str = Field(..., description="Unique snake_case identifier for the node, e.g., 'cragmaw_cave_01'.")
    name: str = Field(..., description="The narrative name of the room or point of interest.")
    description: str = Field(..., description="The static read-aloud or narrative baseline description of the area.")
    
    # ─── Spatial Pointers (Adjacency List) ───
    connected_node_ids: List[str] = Field(
        ..., 
        description="List of node_ids that a player can physically move to from this location."
    )
    
    # ─── State & Environment Engine ───
    parent_alert_flags: Dict[str, bool] = Field(
        default_factory=dict, 
        description="Pre-seeded static threshold flags that dictate map safety, e.g., {'mill_on_alert': true}."
    )
    
    # ─── Interactions ───
    encounters: Optional[List[NodeEncounterDTO]] = Field(
        default=None, 
        description="List of monsters natively stationed in this room."
    )
    loot: Optional[List[str]] = Field(
        default=None, 
        description="List of item names, artifacts, or gold amounts found hidden or in plain sight."
    )
    traps_or_hazards: Optional[List[str]] = Field(
        default=None,
        description="Descriptions of environmental dangers, DCs, or traps present in the node."
    )
    
    model_config = {"extra": "forbid"}

class AdventureDTO(BaseModel):
    """
    Root model passed to `gemini_service` for structured output extraction.
    Forces Gemini to return the entire adventure module as a flat array of nodes.
    """
    module_id: str = Field(..., description="The global tracking ID of the adventure module, e.g., 'lmop'.")
    module_name: str = Field(..., description="The readable title of the adventure.")
    
    # ─── Flat Document Pipeline ───
    nodes: List[NodeDTO] = Field(
        ..., 
        description="The completely flattened array of all rooms, locations, and points of interest."
    )
    
    model_config = {"extra": "forbid"}