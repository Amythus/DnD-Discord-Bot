from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID
from beanie import Document, Indexed
from pydantic import BaseModel, Field
from .delta import PlayerSessionState, EncounterState  # Automatically pulls the new split-node state!

class SavedSessionDelta(Document):
    """
    The persistent snapshot of a completed game session's mutations.
    Created during the /end_session teardown loop by copying the active SessionDelta.
    """
    # Unique campaign index lookup key
    session_id: Indexed(UUID, unique=True)
    
    # Timestamp tracking exactly when this session was archived
    saved_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Persistent storage of character-specific relative counters AND individual node locations
    character_deltas: Dict[UUID, PlayerSessionState] = Field(default_factory=dict)
    
    # Holds any unresolved encounter turn orders if the GM ended mid-combat
    active_encounter: EncounterState = Field(default_factory=EncounterState)

    class Settings:
        name = "saved_session_deltas"