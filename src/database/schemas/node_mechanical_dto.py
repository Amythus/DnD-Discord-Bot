from pydantic import BaseModel, Field, ConfigDict
from typing import List
from database.models.campaign.adventure_node import (
    NavigationGrid, EnvironmentProfile, EncounterReference,
    SpatialTrigger, EnvironmentalTrap, LocalTreasure, NodeMetadata
)

class NodeMechanicalDTO(BaseModel):
    navigation: NavigationGrid = Field(
        description="The navigation grid containing exits and directional logic. Strict validation required for target_node_id references."
    )
    environment: EnvironmentProfile = Field(
        description="Baseline physics, lighting, and resting safety constraints for the room."
    )
    encounters: List[EncounterReference] = Field(
        default_factory=list,
        description="List of enemies or combatant templates present in the room."
    )
    spatial_triggers: List[SpatialTrigger] = Field(
        default_factory=list,
        description="Systemic triggers that execute logic when player coordinates cross defined boundaries."
    )
    environmental_traps: List[EnvironmentalTrap] = Field(
        default_factory=list,
        description="Hazard definitions with detection DCs and mechanical damage/effect distribution."
    )
    treasure: LocalTreasure = Field(
        description="Inventory of currency and items found within this node."
    )
    node_metadata: NodeMetadata = Field(
        description="Administrative props, traversal flags, and regional tracking information."
    )

    model_config = ConfigDict(extra='forbid')