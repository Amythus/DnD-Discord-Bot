from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID, uuid4
from beanie import Document, Indexed
from pydantic import BaseModel, Field

class CampaignLedger(BaseModel):
    """Tracks narrative progress and world state adjustments for LLM consistency."""
    npc_dispositions: Dict[str, int] = Field(default_factory=dict)
    story_flags: List[str] = Field(default_factory=list)

class ScheduledEvent(BaseModel):
    """Tracks delayed execution mutations or periodic status triggers (e.g., poison ticks)."""
    event_id: UUID = Field(default_factory=uuid4)
    trigger_at_round: int
    trigger_at_turn_index: int
    mutation_type: str
    payload: Dict = Field(default_factory=dict)

class PlayerSessionState(BaseModel):
    """Volatile state tracking for an individual player character within this session."""
    current_node_id: str = Field(default="start_node")
    damage_taken: int = Field(default=0)
    spent_slots: Dict[str, int] = Field(default_factory=dict)
    
    # ADDED: Relative depletion tracking for short rests to avoid level-up state drift
    spent_hit_dice: Dict[str, int] = Field(default_factory=dict) 
    
    has_inspiration: bool = Field(default=False)
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
    """The hot cache buffer stack isolating live chaotic gameplay from master sheets."""
    # session_id: Indexed(UUID, unique=True)
    session_id: UUID
    
    # ADDED: Discord routing tracking for session lookup/saving
    guild_id: str
    initiating_player_id: Optional[str] = None
    
    character_deltas: Dict[UUID, PlayerSessionState] = Field(default_factory=dict)
    active_encounter: EncounterState = Field(default_factory=EncounterState)
    staged_actions: List[StagedAction] = Field(default_factory=list)
    
    # ADDED: Game master layout structures for narrative tracking and time-delayed hooks
    campaign_ledger: CampaignLedger = Field(default_factory=CampaignLedger)
    scheduled_events: List[ScheduledEvent] = Field(default_factory=list)

    # class Settings:
    #     name = "session_deltas"

    #     indexes = [
    #         {
    #             "key": [("session_id", 1)],
    #             "unique": True
    #         },
    #         "guild_id"
    #     ]

    class Settings:
        name = "session_deltas"
        indexes = [
            {
                "key": [("session_id", 1)],
                "unique": True
            },
            "guild_id"
        ]


    class Config:
        schema_extra = {
            "example": {
                "session_id": "123e4567-e89b-12d3-a456-426614174000",
                
                # NEW: Explicit routing metadata mapping to the Discord environment
                "guild_id": "987654321098765432",
                "initiating_player_id": "123456789012345678",
                
                "character_deltas": {
                    "550e8400-e29b-41d4-a716-446655440000": {
                        "current_node_id": "cavern_room_b",
                        "damage_taken": 12,
                        "spent_slots": {"1": 2},
                        
                        # NEW: Tracks spent hit dice by denomination for split level-up protection
                        "spent_hit_dice": {"d8": 1, "d10": 0},
                        
                        "has_inspiration": True,
                        "active_conditions": ["Poisoned"]
                    },
                    "aa1e8400-e29b-41d4-a716-446655441111": {
                        "current_node_id": "cavern_entrance",
                        "damage_taken": 0,
                        "spent_slots": {},
                        "spent_hit_dice": {},
                        "has_inspiration": False,
                        "active_conditions": []
                    }
                },
                "active_encounter": {
                    "is_active": False, 
                    "turn_order": [], 
                    "current_turn_index": 0, 
                    "round_number": 1
                },
                "staged_actions": [],
                
                # NEW: Outlines how story hooks and NPC faction opinions are fed to Gemini
                "campaign_ledger": {
                    "npc_dispositions": {
                        "npc_bob_the_merchant": -2,
                        "faction_harpers": 5
                    },
                    "story_flags": [
                        "killed_goblin_king",
                        "triggered_mill_alert"
                    ]
                },
                
                # NEW: Structural example of your delayed middleware execution hooks
                "scheduled_events": [
                    {
                        "event_id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
                        "trigger_at_round": 3,
                        "trigger_at_turn_index": 2,
                        "mutation_type": "poison_tick",
                        "payload": {
                            "target_character_id": "550e8400-e29b-41d4-a716-446655440000",
                            "damage_dice": "1d4"
                        }
                    }
                ]
            }
        }