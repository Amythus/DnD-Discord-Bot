from typing import List, Dict, Optional
from pydantic import BaseModel, Field

class CharacterClassDTO(BaseModel):
    """Strict schema for handling single or multi-class level splits."""
    class_name: str = Field(..., description="The name of the class, e.g., 'Fighter', 'Wizard'.")
    level: int = Field(..., description="The level the character possesses in this specific class.")
    
    model_config = {"extra": "forbid"}

class DDBParsedCharacter(BaseModel):
    """
    Data Transfer Object for parsing D&D Beyond character sheets via Gemini.
    Strictly forbids extra fields to ensure LLM structured output determinism.
    """
    name: str = Field(..., description="The character's full narrative name.")
    race: str = Field(..., description="The character's species or race.")
    classes: List[CharacterClassDTO] = Field(
        ..., 
        description="Array of the character's classes and their respective levels."
    )
    
    # ─── Persistent Base Stats (The Absolute Truth) ───
    level: int = Field(..., description="The total combined level of the character.")
    max_hp: int = Field(..., description="The absolute maximum hit points of the character (ignoring temporary damage).")
    armor_class: int = Field(..., description="The character's calculated resting armor class.")
    
    # ─── Attributes ───
    strength: int = Field(..., description="Total Strength score (not the modifier).")
    dexterity: int = Field(..., description="Total Dexterity score.")
    constitution: int = Field(..., description="Total Constitution score.")
    intelligence: int = Field(..., description="Total Intelligence score.")
    wisdom: int = Field(..., description="Total Wisdom score.")
    charisma: int = Field(..., description="Total Charisma score.")

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
    
    # ─── Lists & Proficiencies ───
    proficiencies: List[str] = Field(
        default_factory=list,
        description="Combined list of skill, saving throw, tool, and language proficiencies."
    )
    inventory: List[str] = Field(
        default_factory=list,
        description="List of strings representing the names of weapons, armor, and gear actively carried."
    )
    
    # Strictly locks the schema for Gemini API Developer Tier compliance
    model_config = {"extra": "forbid"}