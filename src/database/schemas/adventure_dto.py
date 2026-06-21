from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from database.models.static.node import (
    ExitVector, EnvironmentProfile, SensoryProfile, 
    NodeMetadata, EncounterReference, LootTable, QuestHook
)

# Forbid extra properties globally across all sub-models for the Developer API
ExitVector.model_config["extra"] = "forbid"
EnvironmentProfile.model_config["extra"] = "forbid"
SensoryProfile.model_config["extra"] = "forbid"
NodeMetadata.model_config["extra"] = "forbid"
EncounterReference.model_config["extra"] = "forbid"
LootTable.model_config["extra"] = "forbid"
QuestHook.model_config["extra"] = "forbid"

class NodeDTO(BaseModel):
    """Pure Pydantic twin of Node for schema-locked Gemini execution."""
    model_config = {"extra": "forbid"}

    node_id: str = Field(description="Deterministic snake_case ID. Example: 'cragmaw_hideout_area_1'.")
    parent_node_id: Optional[str] = Field(default=None, description="Relational pointer up to a macro-node/region.")
    node_type: str = Field(description="Must evaluate exactly to one: [CAMPAIGN_ROOT, CITY_OVERWORLD, REGIONAL_DISTRICT, BUILDING_POI, INTERIOR_ROOM].")
    title: str = Field(description="User-facing display name shown in Discord embeddings.")
    
    navigation: Any = Field(description="The map layer layout containing verified exit vectors.")
    environment: EnvironmentProfile = Field(description="Physical rule profiles (lighting, safety bounds).")
    sensory_profile: SensoryProfile = Field(description="Atmorphic details fed to the narrator.")
    node_metadata: NodeMetadata = Field(description="Intelligence metrics housing sandbox tags, room states, and triggers.")
    
    encounters: List[EncounterReference] = Field(default_factory=list)
    treasure: LootTable = Field(default_factory=LootTable)
    interactables: List[Dict[str, Any]] = Field(default_factory=list)
    npc_profiles: List[Dict[str, Any]] = Field(default_factory=list)
    story_hooks: List[str] = Field(default_factory=list)
    campaign_lore: List[str] = Field(default_factory=list)
    llm_contexts: Dict[str, str] = Field(description="Must include a 'baseline_narration' key containing verbatim descriptions.")

class AdventureMatrixResponse(BaseModel):
    """The root response object passed directly as Gemini's response_schema."""
    model_config = {"extra": "forbid"}
    
    adventure_id: str = Field(description="The unique global snake_case string for the entire book. Example: 'lost_mine_of_phandelver'.")
    quest_registry: List[QuestHook] = Field(default_factory=list, description="Master array tracking all overarching game quests found in this chapter/adventure.")
    nodes: List[NodeDTO] = Field(description="The flat matrix graph of all extracted locations within the text.")