from typing import List, Dict, Any, Optional, Union
from beanie import Document, Indexed
from pydantic import BaseModel, Field

class Item(Document):
    """
    Unified Item model handling both mundane base items and magical variations.
    """
    name: Indexed(str)
    source: Indexed(str)
    page: Optional[int] = None
    
    # Intrinsic Properties (populated natively by base items, or hydrated into magic items)
    rarity: Optional[str] = "common"  # base items are common, magic items override this
    weight: Optional[float] = None
    value: Optional[int] = None       # Value in copper pieces or alternative format
    
    # Equipment Specifics
    type_code: Optional[str] = Field(default=None, alias="type")  # e.g., "W" for weapon, "A" for armor
    weapon_category: Optional[str] = Field(default=None, alias="weaponCategory")
    dmg1: Optional[str] = None         # e.g., "1d8"
    dmg_type: Optional[str] = Field(default=None, alias="dmgType")
    properties: Optional[List[str]] = None  # e.g., ["F", "L"] (Finesse, Light)
    
    ac: Optional[int] = None
    
    # Magic / Artifact Specifics
    is_magic: bool = Field(default=False)
    base_item_string: Optional[str] = Field(default=None, alias="baseitem")  # e.g., "longsword|phb"
    
    # --- Spellcasting & Active Charge Properties (Added to prevent extra_forbidden errors) ---
    daily: Optional[Dict[str, Any]] = None      # e.g., {"1e": ["gust of wind"]}
    charges: Optional[int] = None               # Total charges an item holds
    recharge: Optional[str] = None              # Recharge formula (e.g., "1d4 + 1")
    recharge_type: Optional[str] = Field(default=None, alias="rechargeType") # e.g., "dawn"
    attached_spells: Optional[List[str]] = Field(default=None, alias="attachedSpells") # List of spells it grants
    
    # Narrative text descriptions
    entries: Optional[List[Union[str, Dict[str, Any]]]] = Field(default_factory=list)

    class Settings:
        name = "items"  # Maps both source files into a single collection

    model_config = {
        "populate_by_name": True,
        "extra": "forbid"  # Hardens schema for your Gemini API parsing requirements
    }