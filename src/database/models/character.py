from datetime import datetime
from enum import Enum
from beanie import Document, Indexed
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Annotated, Literal

# ==========================================
# 1. ENUMS & CORE TAXONOMY
# ==========================================

class ConditionType(str, Enum):
    BLINDED = "BLINDED"
    CHARMED = "CHARMED"
    DEAFENED = "DEAFENED"
    FRIGHTENED = "FRIGHTENED"
    GRAPPLED = "GRAPPLED"
    INCAPACITATED = "INCAPACITATED"
    INVISIBLE = "INVISIBLE"
    PARALYZED = "PARALYZED"
    PETRIFIED = "PETRIFIED"
    POISONED = "POISONED"
    PRONE = "PRONE"
    RESTRAINED = "RESTRAINED"
    STUNNED = "STUNNED"
    UNCONSCIOUS = "UNCONSCIOUS"

class ActionEconomy(BaseModel):
    action_used: bool = False
    bonus_action_used: bool = False
    reaction_used: bool = False
    movement_spent_ft: int = 0

class ResourcePool(BaseModel):
    """
    Highly volatile session variables. Discord modifies these live. 
    D&D Beyond imports provide the baseline starting point.
    """
    current_hp: int = Field(description="Active session HP. Mutated live via Discord combat.")
    temporary_hp: int = Field(default=0)
    heroic_inspiration: int = Field(default=0, ge=0, le=1)
    exhaustion_level: int = Field(default=0, ge=0, le=6)
    death_saves_success: int = Field(default=0, ge=0, le=3)
    death_saves_failure: int = Field(default=0, ge=0, le=3)
    action_economy: ActionEconomy = Field(default_factory=ActionEconomy)
    custom_pools: Dict[str, int] = Field(
        default_factory=dict, 
        description="Tracks volatile points spent in chat (e.g., {'ki_points_spent': 2, 'rage_uses_spent': 1})."
    )

class CharacterSheet(Document):
    # THE MULTI-KEY IDENTITY ANCHORS (Prevents name duplicate bugs)
    user_id: Annotated[str, Indexed()] = Field(description="The Discord User ID string mapping ownership of this asset.")
    dnd_beyond_id: str = Field(description="The unique numeric ID extracted directly from the character link URL.")
    character_url: str = Field(description="The saved full link to enable quick mid-session re-syncing/pulling.")
    
    # User-facing Display Metric (Mutable, changes if they rename their sheet on D&D Beyond)
    name: str = Field(description="Character name. Used for search display and chat embeds.")
    
    # Flat reference blocks mirrored directly from the latest D&D Beyond API payload snapshot
    classes_summary: str = Field(description="Captured class breakdown string for display (e.g., 'Paladin 3 / Sorcerer 2').")
    level: int = 1
    race: str
    base_armor_class: int
    speed_ft: int = 30
    proficiency_bonus: int
    
    # Stat arrays required by the Python Engine to roll dice
    ability_modifiers: Dict[str, int] = Field(description="Pre-calculated modifiers from D&D Beyond, e.g., {'str': 3, 'dex': -1}")
    saving_throw_modifiers: Dict[str, int] = Field(description="Total save modifiers including proficiency, e.g., {'str': 5, 'con': 2}")
    skill_modifiers: Dict[str, int] = Field(description="Total skill check modifiers including expertise, e.g., {'stealth': 7, 'perception': 1}")
    
    # Active Session Tracking Pools
    resources: ResourcePool
    status_conditions: List[ConditionType] = Field(default_factory=list)
    
    # Simplified Inventory (Just strings/IDs to track weapon names for the chat parser to know what they can attack with)
    equipped_weapons: List[str] = Field(default_factory=list, description="List of attack weapons available, e.g., ['longsword', 'shortbow']")
    known_spells: List[str] = Field(default_factory=list, description="List of prepared/known spell names for active engine validation.")
    
    # Current slot ceilings extracted from D&D Beyond. Session tracking modifies 'used' values.
    spell_slots_max: Dict[str, int] = Field(default_factory=dict, description="Max slots per tier, e.g., {'level_1': 4, 'level_2': 2}")
    spell_slots_used: Dict[str, int] = Field(default_factory=dict, description="Active expenditure pool tracking spent slots inside the chat session.")
    
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "characters"
        # Compound unique index guarantees a user can name multiple characters whatever they want without key collisions
        indexes = [
            [
                ("user_id", 1),
                ("dnd_beyond_id", 1)
            ]
        ]