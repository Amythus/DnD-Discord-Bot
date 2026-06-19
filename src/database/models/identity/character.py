from typing import Dict, List, Optional
from uuid import UUID, uuid4
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

class Character(Document):
    """
    The master baseline character sheet. 
    This is updated strictly during mid-week level-ups or D&D Beyond syncs, 
    NOT during live combat.
    """
    # Unique internal ID (Linked as a Foreign Key in CharacterRegistry)
    character_id: Indexed(UUID, unique=True) = Field(default_factory=uuid4)
    
    # Core Identity
    name: str
    race: str
    classes: Dict[str, int] = Field(default_factory=dict) # e.g., {"rogue": 3, "fighter": 2}
    level: int
    
    # Baseline Combat Stats (The "Ceilings")
    max_hp: int
    armor_class: int
    passive_perception: int
    speed: int
    
    # Core Attributes
    stats: CharacterStats
    
    # Magic System Ceilings
    # Maps spell slot levels to their maximum capacity: e.g., {"1": 4, "2": 3, "pact_1": 2}
    total_spell_slots: Dict[str, int] = Field(default_factory=dict)
    
    # Permanent Inventory & Features
    # These store "slugs" (e.g., "flame-tongue-longsword") that your engine 
    # uses to look up mechanical rules from static/item.py or static/spell.py
    known_spells: List[str] = Field(default_factory=list)
    inventory_slugs: List[str] = Field(default_factory=list)
    attuned_items: List[str] = Field(default_factory=list)
    
    # Wealth
    gold_pieces: float = 0.0

    class Settings:
        name = "identity_characters" # Collection name in MongoDB

    class Config:
        schema_extra = {
            "example": {
                "character_id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Eldrin",
                "race": "High Elf",
                "classes": {"wizard": 5},
                "level": 5,
                "max_hp": 32,
                "armor_class": 15,
                "passive_perception": 14,
                "speed": 30,
                "stats": {
                    "strength": 8, "dexterity": 14, "constitution": 14,
                    "intelligence": 18, "wisdom": 12, "charisma": 10
                },
                "total_spell_slots": {"1": 4, "2": 3, "3": 2},
                "known_spells": ["fireball", "mage-armor", "shield"],
                "inventory_slugs": ["wand-of-magic-missiles", "health-potion"],
                "attuned_items": ["wand-of-magic-missiles"],
                "gold_pieces": 145.5
            }
        }