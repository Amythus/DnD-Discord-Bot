from typing import Dict, List, Optional
from uuid import UUID, uuid4
from datetime import datetime
from beanie import Document, Indexed
from pydantic import BaseModel, Field

class CharacterStats(BaseModel):
    """Sub-model for core D&D attributes."""
    strength: int
    dexterity: int
    constitution: int
    intelligence: int
    wisdom: int
    charisma: int

class CharacterProficiencies(BaseModel):
    """
    Ingested proficiencies used by the engine to compute saving throws,
    skill checks, and utility actions.
    """
    # Lists of strings matching standard 5e slugs (e.g., ["str", "con"])
    saving_throws: List[str] = Field(default_factory=list)
    
    # Simple skill slugs (e.g., ["athletics", "stealth"])
    skills: List[str] = Field(default_factory=list)
    
    # Skills with double proficiency (e.g., ["thieves-tools", "sleight-of-hand"])
    expertise: List[str] = Field(default_factory=list)
    
    # Equipment and utility capabilities (e.g., ["martial-weapons", "heavy-armor", "elven"])
    weapons: List[str] = Field(default_factory=list)
    armor: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)

class Character(Document):
    """
    The master baseline character sheet ceilings.
    Updated exclusively during mid-week level-ups or out-of-session updates.
    """
    # Relational Identifier
    character_id: UUID = Field(default_factory=uuid4)
    
    # Core Identity
    name: str
    race: str
    classes: Dict[str, int] = Field(default_factory=dict) # e.g., {"rogue": 3, "fighter": 2}
    level: int
    
    # Baseline Combat & Initiative Baselines
    max_hp: int
    armor_class: int
    initiative_modifier: int = Field(0, description="Permanent static modifier to initiative rolls from stats/feats.")
    speed: int
    
    # Ingested Passives (All 3 primary 5e passive systems)
    passive_perception: int
    passive_investigation: int = Field(10)
    passive_insight: int = Field(10)
    
    # Core Attributes
    stats: CharacterStats
    
    # Ingested Feats and Capabilities
    proficiencies: CharacterProficiencies = Field(default_factory=CharacterProficiencies)
    feats: List[str] = Field(default_factory=list, description="List of slugged feats, e.g., ['great-weapon-master', 'alert']")
    passive_features: List[str] = Field(default_factory=list, description="Class features like 'cunning-action', 'action-surge'")
    
    # Resource Pool Caps (Ceilings only)
    # E.g., {"1": 4, "2": 3} or {"pact_1": 2}
    total_spell_slots: Dict[str, int] = Field(default_factory=dict)
    # Total historical Hit Dice configuration, e.g., {"d8": 3, "d10": 2}
    total_hit_dice: Dict[str, int] = Field(default_factory=dict)
    
    # Permanent Inventory & Asset Slugs
    known_spells: List[str] = Field(default_factory=list)
    inventory_slugs: List[str] = Field(default_factory=list)
    attuned_items: List[str] = Field(default_factory=list)
    
    # Wealth
    gold_pieces: float = 0.0

    # Synchronization Heartbeat
    last_synced_at: Optional[datetime] = Field(None)

    # class Settings:
    #     name = "identity_characters"

    #     indexes = [
    #         {
    #             "key": [("character_id",1)],
    #             "unique": True
    #         }
    #     ]

    class Settings:
        name = "identity_characters"
        indexes = [
            {
                "key": [("character_id", 1)],
                "unique": True
            }
        ]


    class Config:
        schema_extra = {
            "example": {
                "character_id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Eldrin",
                "race": "High Elf",
                "classes": {"rogue": 3, "fighter": 2},
                "level": 5,
                "max_hp": 38,
                "armor_class": 16,
                "initiative_modifier": 4,
                "speed": 30,
                "passive_perception": 14,
                "passive_investigation": 12,
                "passive_insight": 11,
                "stats": {
                    "strength": 10, "dexterity": 18, "constitution": 14,
                    "intelligence": 12, "wisdom": 12, "charisma": 10
                },
                "proficiencies": {
                    "saving_throws": ["dex", "int"],
                    "skills": ["athletics", "acrobatic", "stealth", "perception"],
                    "expertise": ["stealth"],
                    "weapons": ["simple-weapons", "martial-weapons"],
                    "armor": ["light-armor", "medium-armor"],
                    "tools": ["thieves-tools"],
                    "languages": ["common", "elvish", "thieves-cant"]
                },
                "feats": ["alert"],
                "passive_features": ["cunning-action", "action-surge", "second-wind"],
                "total_spell_slots": {},
                "total_hit_dice": {"d8": 3, "d10": 2},
                "known_spells": [],
                "inventory_slugs": ["rapier", "stud-leather", "health-potion"],
                "attuned_items": [],
                "gold_pieces": 250.0,
                "last_synced_at": "2026-06-19T21:30:00Z"
            }
        }