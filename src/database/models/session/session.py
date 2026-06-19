from pydantic import BaseModel, Field
from beanie import Document, Indexed
from typing import Dict, Any, List, Optional
from datetime import datetime

class StagedAction(BaseModel):
    """Holds a structured action that is waiting for player input (e.g., button click)."""
    action_id: str  # Unique UUID for the transaction
    action_type: str  # e.g., "short_rest_resolution", "saving_throw_prompt"
    payload: Dict[str, Any]  # The raw JSON policy data emitted by Gemini
    expires_at: datetime

class CampaignCharacterDelta(BaseModel):
    """Tracks fluid variations and resource drains for a character within an isolated campaign."""
    # The Math Engine Core: Python calculates totals using these relative drains
    damage_taken: int = 0  # Python Logic: current_hp = max_hp - damage_taken
    temporary_hp: int = 0
    spent_hit_dice: int = 0
    
    # Tracks resource drains explicitly mapped by level strings
    # e.g., {"level_1": 2} -> Means two 1st-level slots are missing/expended
    expended_spell_slots: Dict[str, int] = Field(default_factory=dict)
    
    # Transitory or campaign-locked properties
    temporary_statuses: List[str] = Field(default_factory=list)  # ["poisoned", "stunned"]
    campaign_loot: List[Dict[str, Any]] = Field(default_factory=list)  # Earned item drops unique to this game

class SavedSessionDelta(Document):
    """The complete episodic campaign snapshot overlay."""
    campaign_id: Indexed(str, unique=True)
    guild_id: str
    active_node_id: str
    
    character_states: Dict[str, CampaignCharacterState] = Field(default_factory=dict)
    session_room_states: Dict[str, NodeMutation] = Field(default_factory=dict)
    active_staged_actions: Dict[str, StagedAction] = Field(default_factory=dict)
    active_encounter: ActiveEncounter = Field(default_factory=ActiveEncounter)
    campaign_ledger: LongTermCampaignLedger = Field(default_factory=LongTermCampaignLedger)
    
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "saved_session_deltas"

class SessionDelta(Document):
    """The complete episodic campaign snapshot overlay."""
    campaign_id: Indexed(str, unique=True)
    guild_id: str
    active_node_id: str
    
    # Character, Room, and Staged Engine Sandboxes
    character_states: Dict[str, CampaignCharacterState] = Field(default_factory=dict)
    session_room_states: Dict[str, NodeMutation] = Field(default_factory=dict)
    active_staged_actions: Dict[str, StagedAction] = Field(default_factory=dict)
    
    # --- Campaign State ---
    active_encounter: ActiveEncounter = Field(default_factory=ActiveEncounter)
    campaign_ledger: LongTermCampaignLedger = Field(default_factory=LongTermCampaignLedger)
    
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "session_deltas"