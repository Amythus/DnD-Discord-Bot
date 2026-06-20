from typing import List, Dict, Any, Optional, Union
from beanie import Document, Indexed
from pydantic import BaseModel, Field

class MonsterTypeDetail(BaseModel):
    type: str
    tags: Optional[List[str]] = None

class ArmorClassDetail(BaseModel):
    ac: int
    from_source: Optional[List[str]] = Field(default=None, alias="from")

    # Fixed Configuration Key naming convention for V2
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
    average: int
    formula: Optional[str] = None

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
    srd: Optional[bool] = False
    referenceSources: Optional[List[str]] = None
    reprintedAs: Optional[List[str]] = None
    size: List[str]
    
    type: Union[str, MonsterTypeDetail]
    alignment: Optional[List[str]] = None
    
    ac: List[Union[int, ArmorClassDetail]]
    hp: HitPoints
    speed: Dict[str, int]
    
    # Core Attributes
    str: int
    dex: int
    con: int
    int: int
    wis: int
    cha: int
    
    # CRITICAL REFAC: Renamed variable to prevent shadowing Document.save()
    saving_throws: Optional[Dict[str, str]] = Field(default=None, alias="save")
    
    skill: Optional[Dict[str, str]] = None
    senses: Optional[List[str]] = None
    passive: int
    languages: Optional[List[str]] = None
    cr: str
    
    # Mechanics Block Arrays
    trait: Optional[List[ActionOrTrait]] = None
    action: Optional[List[ActionOrTrait]] = None
    legendary: Optional[List[ActionOrTrait]] = None
    legendaryGroup: Optional[LegendaryGroup] = None
    environment: Optional[List[str]] = None
    
    # Metadata Layers
    soundClip: Optional[SoundClip] = None
    attachedItems: Optional[List[str]] = None
    languageTags: Optional[List[str]] = None
    damageTags: Optional[List[str]] = None
    damageTagsLegendary: Optional[List[str]] = None
    conditionInflict: Optional[List[str]] = None
    conditionInflictLegendary: Optional[List[str]] = None
    savingThrowForced: Optional[List[str]] = None
    savingThrowForcedLegendary: Optional[List[str]] = None
    miscTags: Optional[List[str]] = None
    
    hasToken: Optional[bool] = False
    hasFluff: Optional[bool] = False
    hasFluffImages: Optional[bool] = False

    class Settings:
        name = "monsters"

    # Fixed Configuration dictionary usage pattern for Pydantic V2 Document hooks
    model_config = {
        "populate_by_name": True
    }