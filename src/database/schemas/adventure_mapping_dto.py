from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class NodeExitDTO(BaseModel):
    direction: str = Field(
        ..., 
        description="The directional keyword vector (e.g., 'north', 'south', 'down', 'secret_passage')."
    )
    target_node_id: str = Field(
        ..., 
        description="The snake_case ID of the target node destination (can be a placeholder room ID derived from context)."
    )


class NodeDTO(BaseModel):
    """Represents a single structural element within the map graph skeleton."""
    node_id: str = Field(
        ..., 
        description="Unique snake_case identifier representing this room or area."
    )
    parent_id: Optional[str] = Field(
        default=None, 
        description="Optional parent structural identifier representing an overarching dungeon layer, floor, or region."
    )
    exits: List[NodeExitDTO] = Field(
        default_factory=list, 
        description="List of all topological movement vectors extending from this node."
    )


class AdventureMapDTO(BaseModel):
    """
    Pass 1 Master DTO: Wraps the entire extracted node matrix into a single 
    structured payload for clean batch ingestion validation.
    """
    adventure_id: str = Field(
        ..., 
        description="Global snake_case identifier grouping all nodes within this campaign blueprint."
    )
    nodes: List[TopologicalNodeDTO] = Field(
        ..., 
        description="The complete list of all structural nodes discovered in the source raw text."
    )

    # Enforce strict parsing constraints across the entire extraction container
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "adventure_id": "lost_mine_of_phandelver",
                "nodes": [
                    {
                        "node_id": "cragmaw_hideout_cave_mouth",
                        "parent_id": "cragmaw_hideout",
                        "exits": [
                            {"direction": "north", "target_node_id": "cragmaw_hideout_kennels"},
                            {"direction": "east", "target_node_id": "cragmaw_hideout_overlook"}
                        ]
                    },
                    {
                        "node_id": "cragmaw_hideout_kennels",
                        "parent_id": "cragmaw_hideout",
                        "exits": [
                            {"direction": "south", "target_node_id": "cragmaw_hideout_cave_mouth"}
                        ]
                    }
                ]
            }
        }
    )