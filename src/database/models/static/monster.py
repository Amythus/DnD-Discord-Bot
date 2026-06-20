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
    average: int
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
    size: List[str]
    
    # Structural updates for Humanoid tags
    type: Union[str, MonsterTypeDetail, Dict[str, Any]]
    
    # Fixed Cloud Giant / Empyrean percentage arrays
    alignment: Optional[List[Union[str, Dict[str, Any]]]] = None
    
    ac: List[Union[int, ArmorClassDetail, Dict[str, Any]]]
    hp: HitPoints
    
    # Fixed Air Elemental hover/Werewolf shape conditions
    speed: Dict[str, Union[int, bool, Dict[str, Any]]]
    
    # Core Attributes (Renamed 'int' attribute to prevent module-level namespace conflicts)
    str: int
    dex: int
    con: int
    intelligence: int = Field(alias="int")
    wis: int
    cha: int
    
    # Prevent shadowing Document.save()
    saving_throws: Optional[Dict[str, int]] = Field(default=None, alias="save")
    
    skill: Optional[Dict[str, Union[int, str]]] = None
    senses: Optional[List[str]] = None
    passive: Union[int, str]
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

    model_config = {
        "populate_by_name": True
    }