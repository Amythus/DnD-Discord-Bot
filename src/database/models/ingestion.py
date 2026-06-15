from typing import List, Dict, Optional
from pydantic import BaseModel, Field, ConfigDict
from .character import CharacterAttributes, CharacterVitals, Item, SpellSlotTracker

# Create a master configuration override dictionary
dev_api_config = ConfigDict(extra="allow")

# --- Update your nested validation wrappers to drop the strict property flag ---
class CleanAttributes(CharacterAttributes):
    model_config = dev_api_config
    model_config = ConfigDict(extra="allow")

class CleanVitals(CharacterVitals):
    model_config = dev_api_config
    model_config = ConfigDict(extra="allow")

class CleanItem(Item):
    model_config = dev_api_config
    model_config = ConfigDict(extra="allow")

class CleanSpellSlots(SpellSlotTracker):
    model_config = dev_api_config
    model_config = ConfigDict(extra="allow")

# --- The Master Ingestion Class Passed to Gemini ---
class CharacterSheetIngestionSchema(BaseModel):
    """
    Primitive schema engineered for Gemini Developer API.
    Forces extra="allow" to scrub the restricted additionalProperties flag.
    """
    model_config = dev_api_config # <--- CRITICAL: Stops Gemini Developer API crashes
    model_config = ConfigDict(extra="allow")

    name: str
    character_class: str = Field(alias="class")
    level: int = 1
    race: str
    background: str
    alignment: str
    experience_points: int = 0
    
    attributes: CleanAttributes
    vitals: CleanVitals
    
    proficiencies: List[str] = Field(default_factory=list)
    status_conditions: List[str] = Field(default_factory=list)
    features_and_traits: Dict[str, str] = Field(default_factory=dict)
    
    inventory: List[CleanItem] = Field(default_factory=list)
    gold_pieces: int = 0
    
    known_spells: List[str] = Field(default_factory=list)
    spell_slots: CleanSpellSlots = Field(default_factory=CleanSpellSlots)
