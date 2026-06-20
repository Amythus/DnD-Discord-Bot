from typing import List, Dict, Any, Optional, Union
from beanie import Document, Indexed
from pydantic import BaseModel, Field

class MonsterTypeDetail(BaseModel):
    type: str
    tags: Optional[List[str]] = None

class ArmorClassDetail(BaseModel):
    ac: int
    from_source: Optional[List[str]] = Field(default=None, alias="from")

    class Config:
        populate_by_name = True

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
    name: Indexed(str, unique=True) # Ensure optimized unique lookups
    source: str
    page: Optional[int] = None
    srd: Optional[bool] = False
    referenceSources: Optional[List[str]] = None
    reprintedAs: Optional[List[str]] = None
    size: List[str]
    
    # Polymorphic field: string ("aberration") or dict ({"type": "humanoid", "tags": [...]})
    type: Union[str, MonsterTypeDetail]
    alignment: Optional[List[str]] = None
    
    # Polymorphic list: numbers ([12]) or structural dicts ([{"ac": 17, "from": ["natural armor"]}])
    ac: List[Union[int, ArmorClassDetail]]
    hp: HitPoints
    speed: Dict[str, int]
    
    # Ability Scores
    str: int
    dex: int
    con: int
    int: int
    wis: int
    cha: int
    
    # Optional Mechanics Maps
    save: Optional[Dict[str, str]] = None
    skill: Optional[Dict[str, str]] = None
    senses: Optional[List[str]] = None
    passive: int
    languages: Optional[List[str]] = None
    cr: str # Kept as string to seamlessly store fractional cr values like "1/4" or "1/8"
    
    # Rules Blocks
    trait: Optional[List[ActionOrTrait]] = None
    action: Optional[List[ActionOrTrait]] = None
    legendary: Optional[List[ActionOrTrait]] = None
    legendaryGroup: Optional[LegendaryGroup] = None
    environment: Optional[List[str]] = None
    
    # Metadata Tags
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
    
    # Media structural indicators
    hasToken: Optional[bool] = False
    hasFluff: Optional[bool] = False
    hasFluffImages: Optional[bool] = False

    class Settings:
        name = "monsters" # MongoDB collection name

    class Config:
        populate_by_name = True