from pydantic import BaseModel, Field, ConfigDict
from typing import List
from database.models.campaign.adventure_node import (
    SensoryProfile, NPCProfile, LocalQuestHook, LLMContexts
)

class NodeNarrativeDTO(BaseModel):
    title: str = Field(
        description="The formal heading of the area parsed from the source markdown."
    )
    sensory_profile: SensoryProfile = Field(
        description="Evocative description of visual, auditory, and olfactory stimuli. Leverage D&D tropes for atmospheric quality."
    )
    npc_profiles: List[NPCProfile] = Field(
        default_factory=list,
        description="Unique interactive NPCs present. Include agendas and conversational hooks based on the narrative context."
    )
    story_hooks: List[str] = Field(
        default_factory=list,
        description="Narrative context or plot-advancing blurbs revealed in this environment."
    )
    quests: List[LocalQuestHook] = Field(
        default_factory=list,
        description="Quest-related relational hooks and objectives tied to this specific location."
    )
    campaign_lore: List[str] = Field(
        default_factory=list,
        description="Historical or world-building entries suitable for character discovery."
    )
    llm_contexts: LLMContexts = Field(
        description="Atmospheric baseline narration. Expand and refine based on cached D&D core rulebook knowledge."
    )

    model_config = ConfigDict(extra='forbid')