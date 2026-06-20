from typing import List, Dict, Any, Optional, Union
from beanie import Document, Indexed
from pydantic import BaseModel, Field

class MonsterTypeTagDetail(BaseModel):
    tag: str
    prefix: Optional[str] = None
    prefixHidden: Optional[bool] = None

class MonsterTypeChoiceDetail(BaseModel):
    choose: List[str]

class MonsterTypeDetail(BaseModel):
    type: Union[str, MonsterTypeChoiceDetail]
    tags: Optional[List[Union[str, MonsterTypeTagDetail]]] = None

class ArmorClassDetail(BaseModel):
    ac: int
    from_source: Optional[List[str]] = Field(default=None, alias="from")

    model_config = {
        "populate_by_name": True
    }

class SpecialArmorClassDetail(BaseModel):
    special: str

class HitPoints(BaseModel):
    average: Optional[int] = None
    formula: Optional[str] = None

class SpecialHitPoints(BaseModel):
    special: str

class ActionOrTrait(BaseModel):
    name: str
    entries: List[Union[str, Dict[str, Any]]]

class LegendaryGroup(BaseModel):
    name: str
    source: str

class SoundClip(BaseModel):
    type: str
    path: str

class ChallengeRatingDetail(BaseModel):
    cr: str
    lair: Optional[str] = None
    regional: Optional[str] = None

class SpecialAlignmentDetail(BaseModel):
    special: str

class ArrayAlignmentDetail(BaseModel):
    alignment: List[str]

class Monster(Document):
    name: Indexed(str, unique=True)
    source: str
    page: Optional[int] = None
    srd: Optional[bool] = False
    referenceSources: Optional[List[str]] = None
    reprintedAs: Optional[List[str]] = None
    size: List[str]
    
    type: Union[str, MonsterTypeDetail, Dict[str, Any]]
    alignment: Optional[List[Union[str, SpecialAlignmentDetail, ArrayAlignmentDetail, Dict[str, Any]]]] = None
    
    ac: Optional[List[Union[int, ArmorClassDetail, SpecialArmorClassDetail]]] = None
    hp: Optional[Union[HitPoints, SpecialHitPoints]] = None
    speed: Optional[Dict[str, Any]] = None
    
    # Ability Scores
    strength: Optional[int] = Field(default=None, alias="str")
    dexterity: Optional[int] = Field(default=None, alias="dex")
    constitution: Optional[int] = Field(default=None, alias="con")
    intelligence: Optional[int] = Field(default=None, alias="int")
    wisdom: Optional[int] = Field(default=None, alias="wis")
    charisma: Optional[int] = Field(default=None, alias="cha")
    
    save: Optional[Dict[str, str]] = None
    skill: Optional[Any] = None
    senses: Optional[List[str]] = None
    
    # HARDENED: Accommodates integer scores as well as calculation formulas like "10 + (PB × 2)"
    passive: Optional[Union[int, str]] = None
    
    languages: Optional[List[str]] = None
    cr: Optional[Union[str, ChallengeRatingDetail]] = None
    
    trait: Optional[List[ActionOrTrait]] = None
    action: Optional[List[ActionOrTrait]] = None
    legendary: Optional[List[ActionOrTrait]] = None
    legendaryGroup: Optional[LegendaryGroup] = None
    environment: Optional[List[str]] = None
    
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