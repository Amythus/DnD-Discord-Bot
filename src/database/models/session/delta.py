from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID, uuid4
from beanie import Document, Indexed
from pydantic import BaseModel, Field

class PlayerSessionState(BaseModel):
    """
    Volatile state tracking for an individual player character within this session.
    Tracks relative metrics and decoupled spatial positioning to allow party splitting.
    """
    # MOVED HERE: Tracks exactly which room/point-of-interest this specific character occupies.
    current_node_id: str = Field(default="start_node")

    # Track accumulated damage rather than absolute current HP.
    # Formula: Current HP = Character.max_hp - PlayerSessionState.damage_taken
    damage_taken: int = Field(default=0)
    
    # Tracks slots actively consumed: e.g., {"1": 2, "3": 1}
    spent_slots: Dict[str, int] = Field(default_factory=dict)
    
    # Under 2024 rules, Heroic Inspiration is volatile and rest/session-bound.
    has_inspiration: bool = Field(default=False)
    
    # Track transient status conditions during an active session
    active_conditions: List[str] = Field(default_factory=list) 

class StagedAction(BaseModel):
    """Temporary action prompt awaiting user validation to prevent button double-clicks."""
    action_id: UUID = Field(default_factory=uuid4)
    player_id: UUID 
    action_type: str 
    payload: Dict = Field(default_factory=dict) 
    expires_at: datetime

class EncounterState(BaseModel):
    """Volatile operational sub-state mapping active combat tracking mechanics."""
    is_active: bool = Field(default=False)
    turn_order: List[str] = Field(default_factory=list) 
    current_turn_index: int = Field(default=0)
    round_number: int = Field(default=1)

class SessionDelta(Document):
    """
    The hot cache buffer stack. Isolates real-time, chaotic message loops
    from the Master Record (Character Registry/Character sheets).
    """
    # Shared Campaign Master session identifier link
    session_id: Indexed(UUID, unique=True)
    
    # Player-specific volatile states indexed by their character UUID
    character_deltas: Dict[UUID, PlayerSessionState] = Field(default_factory=dict)
    
    # Live encounter tracking module data
    active_encounter: EncounterState = Field(default_factory=EncounterState)
    
    # Multi-user thread safety lock arrays
    staged_actions: List[StagedAction] = Field(default_factory=list)

    class Settings:
        name = "session_deltas"

    class Config:
        schema_extra = {
            "example": {
                "session_id": "123e4567-e89b-12d3-a456-426614174000",
                "character_deltas": {
                    "550e8400-e29b-41d4-a716-446655440000": {
                        "current_node_id": "cavern_room_b",  # <--- Rogue is in Room B
                        "damage_taken": 12,
                        "spent_slots": {"1": 2},
                        "has_inspiration": True,
                        "active_conditions": ["Poisoned"]
                    },
                    "aa1e8400-e29b-41d4-a716-446655441111": {
                        "current_node_id": "cavern_entrance", # <--- Paladin is at the Entrance
                        "damage_taken": 0,
                        "spent_slots": {},
                        "has_inspiration": False,
                        "active_conditions": []
                    }
                },
                "active_encounter": {"is_active": False, "turn_order": [], "current_turn_index": 0, "round_number": 1},
                "staged_actions": []
            }
        }