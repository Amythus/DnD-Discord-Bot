from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID
from beanie import Document, Indexed
from pydantic import BaseModel, Field
from .delta import PlayerSessionState, EncounterState, CampaignLedger, ScheduledEvent
from pymongo import IndexModel, ASCENDING, DESCENDING


class SavedSessionDelta(Document):
    """
    The persistent snapshot of a completed game session's mutations.
    Created during the /end_session teardown loop by copying the active SessionDelta.
    """
    # Unique campaign index lookup key
    # session_id: Indexed(UUID)  # Note: Removed unique=True to allow historical snapshot versions
    session_id: UUID
    
    # NEW: Secure multi-server routing index matching the initiating environment
    # guild_id: Indexed(str)
    guild_id: str
    initiating_player_id: Optional[str] = None
    
    # NEW: Linear ordering metrics to distinguish the absolute latest state (HEAD) 
    # from historical forks or rollback points during a campaign resumption handshake
    sequence_number: int = Field(default=1)
    is_active_head: Indexed(bool) = Field(default=True)
    
    # Timestamp tracking exactly when this session was archived
    saved_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Persistent storage of character-specific relative counters AND individual node locations
    character_deltas: Dict[UUID, PlayerSessionState] = Field(default_factory=dict)
    
    # Holds any unresolved encounter turn orders if the GM ended mid-combat
    active_encounter: EncounterState = Field(default_factory=EncounterState)
    
    # NEW: Retains world state flags and faction standings so narrative consistency 
    # is perfectly reloaded by Gemini upon game resumption
    campaign_ledger: CampaignLedger = Field(default_factory=CampaignLedger)
    
    # NEW: Persists un-triggered countdown hooks, traps, or status effects across pauses
    scheduled_events: List[ScheduledEvent] = Field(default_factory=list)

    class Settings:
        name = "saved_session_deltas"
        indexes = [
            "guild_id",
            # Ensure these are native lists of tuples
            [("session_id", 1), ("is_active_head", -1)],
            [("session_id", 1), ("sequence_number", -1)]
        ]
        