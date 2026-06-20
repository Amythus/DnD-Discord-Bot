from typing import List, Dict, Any, Optional, Union
from beanie import Document, Indexed
from pydantic import BaseModel, Field

class MonsterTypeDetail(BaseModel):
    type: str
    tags: Optional[List[Union[str, Dict[str, Any]]]] = None

class ArmorClassDetail(BaseModel):
    ac: int
    from_source: Optional[List[str]] = Field(default=None, alias="from")
    condition: Optional[str] = None

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "example": {
                "ac": 17,
                "from": ["natural armor"]
            }
        }
    }

class HitPoints(BaseModel):
    # FIX 1: Make average optional to handle companion scaling/narrative hp
    average: Optional[int] = None
    formula: Optional[str] = None
    special: Optional[Union[str, Dict[str, Any]]] = None

class ActionOrTrait(BaseModel):
    name: str
    entries: List[Union[str, Dict[str, Any]]]

class LegendaryGroup(BaseModel):
    name: str
    source: str

class SoundClip(BaseModel):
    type: str
    path: str

class Monster(Document):
    name: Indexed(str, unique=True)
    source: str
    page: Optional[int] = None
    srd: Optional[Union[bool, str]] = False
    referenceSources: Optional[List[str]] = None
    reprintedAs: Optional[List[str]] = None
    size: Optional[List[str]] = None  # Softened for minimal placeholders
    
    # Structural updates for Humanoid tags
    type: Optional[Union[str, MonsterTypeDetail, Dict[str, Any]]] = None
    
    # Fixed Cloud Giant / Empyrean percentage arrays
    alignment: Optional[List[Union[str, Dict[str, Any]]]] = None
    
    # FIX 2: Soften core stats to Optional to support narrative/placeholder NPCs
    ac: Optional[List[Union[int, ArmorClassDetail, Dict[str, Any]]]] = None
    hp: Optional[HitPoints] = None
    speed: Optional[Dict[str, Union[int, bool, Dict[str, Any]]]] = None
    
    # Core Attributes made optional to prevent crashes on non-combatant tokens
    str: Optional[int] = None
    dex: Optional[int] = None
    con: Optional[int] = None
    intelligence: Optional[int] = Field(default=None, alias="int")
    wis: Optional[int] = None
    cha: Optional[int] = None
    
    # Prevent shadowing Document.save()
    saving_throws: Optional[Dict[str, int]] = Field(default=None, alias="save")
    
    skill: Optional[Dict[str, Union[int, str]]] = None
    senses: Optional[List[str]] = None
    passive: Optional[Union[int, str]] = None
    languages: Optional[List[str]] = None
    
    # Fixed Beholder lair action modifications
    cr: Optional[Union[str, Dict[str, Any]]] = None
    
    # Mechanics Block Arrays
    trait: Optional[List[ActionOrTrait]] = None
    action: Optional[List[ActionOrTrait]] = None
    bonus: Optional[List[ActionOrTrait]] = None
    reaction: Optional[List[ActionOrTrait]] = None
    legendary: Optional[List[ActionOrTrait]] = None
    mythic: Optional[List[ActionOrTrait]] = None
    legendaryGroup: Optional[LegendaryGroup] = None
    environment: Optional[List[str]] = None
    
    # Metadata Layers
    soundClip: Optional[SoundClip] = None
    attachedItems: Optional[List[str]] = None
    languageTags: Optional[List[str]] = None
    damageTags: Optional