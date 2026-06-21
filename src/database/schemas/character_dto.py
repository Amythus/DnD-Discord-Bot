from typing import List, Dict, Optional
from pydantic import BaseModel, Field, ConfigDict

class CharacterProficienciesDTO(BaseModel):
    """Schema mirroring CharacterProficiencies for structured ingestion."""
    saving_throws: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    expertise: List[str] = Field(default_factory=list)
    weapons: List[str] = Field(default_factory=list)
    armor: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)
    model_config = {"extra": "forbid"}

class CharacterStatsDTO(BaseModel):
    strength: int
    dexterity: int
    constitution: int
    intelligence: int
    wisdom: int
    charisma: int
    model_config = {"extra": "forbid"}
    
class DDBParsedCharacterDTO(BaseModel):
    """
    Data Transfer Object for parsing D&D Beyond character sheets via Gemini.
    Strictly forbids extra fields to ensure LLM structured output determinism.
    """
    dndb_character_id: int = Field(..., description="The unique numerical ID from D&D Beyond.")

    name: str = Field(..., description="The character's full narrative name.")
    race: str = Field(..., description="The character's species or race.")
    classes: Dict[str, int] = Field(..., description="Mapping of class names to levels.")

    # ─── Persistent Base Stats (The Absolute Truth) ───
    level: int = Field(..., description="The total combined level of the character.")
    max_hp: int = Field(..., description="The absolute maximum hit points of the character (ignoring temporary damage).")
    armor_class: int = Field(..., description="The character's calculated resting armor class.")
    
    # ─── New Combat & Utility Baseline Fields ───
    initiative_modifier: int = Field(0)
    speed: int = Field(...)

    # ─── Passive Systems ───
    passive_perception: int = Field(...)
    passive_investigation: int = Field(10)
    passive_insight: int = Field(10)

    # ─── Attributes ───
    stats: CharacterStatsDTO

    # ─── Structural Arrays & Recovery Pools ───
    # Used to define ceilings so the Session Delta can track relative depletion without level-up drift.
    total_hit_dice: Dict[str, int] = Field(
        ..., 
        description="Static ceiling for hit dice, mapping dice type to count. Example for multiclass: {'d8': 3, 'd10': 2}."
    )
    total_spell_slots: Dict[str, int] = Field(
        default_factory=dict, 
        description="Static ceiling for spell slots, keyed by spell level. Example: {'1': 4, '2': 2}."
    )
    
    # ─── Proficiencies, Features & Assets ───
    proficiencies: CharacterProficienciesDTO
    feats: List[str] = Field(default_factory=list)
    passive_features: List[str] = Field(default_factory=list)

    inventory: List[str] = Field(default_factory=list)
    known_spells: List[str] = Field(default_factory=list)
    attuned_items: List[str] = Field(default_factory=list)

    gold_pieces: float = Field(0.0)

    model_config = ConfigDict(
        extra='forbid',
        populate_by_name=True,
        json_schema_extra = {
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
    )