from typing import List, Dict, Any, Optional, Union
from beanie import Document, Indexed
from pydantic import BaseModel, Field

class TimeDetail(BaseModel):
    number: int
    unit: str

class DistanceDetail(BaseModel):
    type: str
    amount: Optional[int] = None

class RangeDetail(BaseModel):
    type: str
    distance: Optional[DistanceDetail] = None

class ComponentDetail(BaseModel):
    v: Optional[bool] = None
    s: Optional[bool] = None
    m: Optional[Union[str, Dict[str, Any]]] = None

class DurationDetail(BaseModel):
    type: str
    duration: Optional[Dict[str, Any]] = None
    concentration: Optional[bool] = None

class Spell(Document):
    name: Indexed(str, unique=True)
    source: str
    page: Optional[int] = None
    
    # Handles true/false or the SRD alternative string names
    srd: Optional[Union[bool, str]] = False
    basicRules: Optional[Union[bool, str]] = False
    
    referenceSources: Optional[List[str]] = None
    reprintedAs: Optional[List[str]] = None
    level: int
    school: str
    time: List[TimeDetail]
    range: RangeDetail
    components: Optional[ComponentDetail] = None
    duration: List[DurationDetail]
    entries: List[Union[str, Dict[str, Any]]]
    
    # HARDENED: Accommodates both a single scaling rules block or a collection list
    scalingLevelDice: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = None
    
    damageInflict: Optional[List[str]] = None
    savingThrow: Optional[List[str]] = None
    miscTags: Optional[List[str]] = None
    areaTags: Optional[List[str]] = None

    class Settings:
        name = "spells"

    model_config = {
        "populate_by_name": True
    }