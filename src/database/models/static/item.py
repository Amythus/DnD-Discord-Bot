from typing import List, Dict, Any, Optional, Union
from beanie import Document, Indexed
from pydantic import BaseModel, Field, AliasChoices

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
    value: Optional[float] = None       # Changed from int to float
    
    # Equipment Specifics
    type_code: Optional[str] = Field(default=None, alias="type")  # e.g., "W" for weapon, "A" for armor
    weapon_category: Optional[str] = Field(default=None, alias="weaponCategory")

    # --- Existing Weapon fields ---
    dmg1: Optional[str] = None         # e.g., "1d8"
    dmg_type: Optional[str] = Field(default=None, alias="dmgType")
    # Added dmg_types to handle list inputs for damage
    dmg_types: Optional[List[str]] = Field(default=None, alias="dmgTypes")

    # Relaxing fields that now accept complex objects/float
    properties: Optional[List[Union[str, Dict[str, Any]]]] = None
    property: Optional[List[Union[str, Dict[str, Any]]]] = None  # Added property as well to mirror properties
    mastery: Optional[List[Union[str, Dict[str, Any]]]] = None
    ammo_type: Optional[str] = Field(default=None, alias="ammoType")
    firearm: Optional[bool] = None

    # New Weapon/Bonus fields
    range: Optional[str] = None
    age: Optional[str] = None
    type_alt: Optional[str] = Field(default=None, alias="typeAlt")
    dmg2: Optional[str] = None
    dmg_modifier: Optional[List[str]] = Field(default=None, alias="dmgModifier")
    bonus_weapon: Optional[str] = Field(default=None, alias="bonusWeapon")
    bonus_weapon_attack: Optional[str] = Field(default=None, alias="bonusWeaponAttack")
    bonus_ac: Optional[str] = Field(default=None, alias="bonusAc")
    bonus_saving_throw: Optional[str] = Field(default=None, alias="bonusSavingThrow")
    bonus_spell_attack: Optional[str] = Field(default=None, alias="bonusSpellAttack")
    bonus_spell_save_dc: Optional[str] = Field(default=None, alias="bonusSpellSaveDc")
    bonus_ability_check: Optional[str] = Field(default=None, alias="bonusAbilityCheck")
    crit_threshold: Optional[int] = Field(default=None, alias="critThreshold")

    # --- Vehicle Specifics ---
    veh_ac: Optional[int] = Field(default=None, alias="vehAc")
    veh_hp: Optional[int] = Field(default=None, alias="vehHp")
    veh_dmg_thresh: Optional[int] = Field(default=None, alias="vehDmgThresh")
    veh_speed: Optional[float] = Field(default=None, alias="vehSpeed")
    cap_passenger: Optional[int] = Field(default=None, alias="capPassenger")
    cap_cargo: Optional[Union[int, float]] = Field(default=None, alias="capCargo") # Relaxed to float
    crew: Optional[Union[int, str]] = None
    crew_min: Optional[int] = Field(default=None, alias="crewMin")
    crew_max: Optional[int] = Field(default=None, alias="crewMax")
    travel_cost: Optional[int] = Field(default=None, alias="travelCost")
    shipping_cost: Optional[int] = Field(default=None, alias="shippingCost")
    see_also_vehicle: Optional[List[str]] = Field(default=None, alias="seeAlsoVehicle")

    # --- Container / Misc ---
    weight_note: Optional[str] = Field(default=None, alias="weightNote")
    container_capacity: Optional[Dict[str, Any]] = Field(default=None, alias="containerCapacity")
    carrying_capacity: Optional[int] = Field(default=None, alias="carryingCapacity")
    pack_contents: Optional[List[Union[str, Dict[str, Any]]]] = Field(default=None, alias="packContents")
    speed: Optional[Union[int, Dict[str, Any]]] = None
    grants_proficiency: Optional[bool] = Field(default=None, alias="grantsProficiency")
    ac: Optional[int] = None
    dexterity_max: Optional[int] = Field(default=None, alias="dexterityMax")
    bar_dimensions: Optional[Dict[str, float]] = Field(default=None, alias="barDimensions")
    # --- Magic / Artifact Specifics ---
    is_magic: bool = Field(default=False)
    base_item_ref: Optional[Union[str, List[str]]] = Field(
        default=None,
        alias="baseitem",
        validation_alias=AliasChoices("baseitem", "baseItem")
    )
    wondrous: Optional[bool] = None
    tattoo: Optional[bool] = None
    sentient: Optional[bool] = None
    curse: Optional[bool] = None
    staff: Optional[bool] = None
    # Ability can be a dict (set/mod) or int (bonus)
    ability: Optional[Union[Dict[str, Any], int]] = None
    grants_language: Optional[bool] = Field(default=None, alias="grantsLanguage")
    modify_speed: Optional[Dict[str, Any]] = Field(default=None, alias="modifySpeed")
    resist: Optional[List[str]] = None
    immune: Optional[List[str]] = None
    condition_immune: Optional[List[str]] = Field(default=None, alias="conditionImmune")
    stealth: Optional[bool] = None
    # Relax types to Union to handle varied schema input
    req_attune: Optional[Union[bool, str, List[Dict[str, Any]]]] = Field(default=None, alias="reqAttune")
    req_attune_tags: Optional[List[Dict[str, Any]]] = Field(default=None, alias="reqAttuneTags")
    text_note: Optional[str] = Field(default=None, alias="text") # Field often labeled "text" in JSON
    
    # Poison & Item properties
    poison: Optional[bool] = None
    poison_types: Optional[List[str]] = Field(default=None, alias="poisonTypes")
    # --- Spellcasting & Active Charge Properties ---
    daily: Optional[Dict[str, Any]] = None      # e.g., {"1e": ["gust of wind"]}
    # Charges can be a raw integer or a string formula like {@dice 1d6 + 1}
    charges: Optional[Union[int, str]] = None               # Total charges an item holds
    recharge: Optional[str] =              None              # Recharge formula (e.g., "1d4 + 1")
    recharge_amount: Optional[Union[int, str]] = Field(default=None, alias="rechargeAmount")
    recharge_type: Optional[str] = Field(default=None, alias="rechargeType") # e.g., "dawn"
    # Attached spells can be a list or a dictionary-based configuration
    attached_spells: Optional[Union[List[str], Dict[str, Any]]] = Field(default=None, alias="attachedSpells") # List of spells it grants
    
    # --- Meta and Fluff fields ---
    scf: Optional[bool] = None
    scf_type: Optional[str] = Field(default=None, alias="scfType")
    has_fluff: Optional[bool] = Field(default=None, alias="hasFluff")
    has_fluff_images: Optional[bool] = Field(default=None, alias="hasFluffImages")
    has_refs: Optional[bool] = Field(default=None, alias="hasRefs")
    detail1: Optional[str] = None
    detail2: Optional[str] = None
    tier: Optional[Union[str, List[str]]] = None
    alias: Optional[List[str]] = None
    optional_features: Optional[List[str]] = Field(default=None, alias="optionalfeatures")
    class_features: Optional[List[str]] = Field(default=None, alias="classFeatures")
    loot_tables: Optional[List[str]] = Field(default=None, alias="lootTables")
    other_sources: Optional[List[Dict[str, Any]]] = Field(default=None, alias="otherSources")
    additional_sources: Optional[List[Dict[str, Any]]] = Field(default=None, alias="additionalSources")
    additional_entries: Optional[List[Any]] = Field(default=None, alias="additionalEntries")
    # Relaxing srd to support potential string values like "Efficient Quiver"
    srd: Optional[Union[bool, str]] = None
    basic_rules: Optional[bool] = Field(default=None, alias="basicRules")
    basic_rules_2024: Optional[bool] = Field(default=None, alias="basicRules2024")

    # Narrative text descriptions
    entries: Optional[List[Union[str, Dict[str, Any]]]] = Field(default_factory=list)
    # Added ability to store requirement lists as lists of strings
    req: Optional[List[Dict[str, Any]]] = None

    # Newly identified fields
    group: Optional[List[str]] = None
    light: Optional[List[Dict[str, Any]]] = None
    misc_tags: Optional[List[str]] = Field(default=None, alias="miscTags")
    reference_sources: Optional[List[str]] = Field(default=None, alias="referenceSources")
    # Reprinted as can be a simple string or a complex object
    reprinted_as: Optional[List[Union[str, Dict[str, Any]]]] = Field(default=None, alias="reprintedAs")

    # --- New Weapon/Bonus fields ---
    strength: Optional[Union[str, int]] = None
    spell_scroll_level: Optional[int] = Field(default=None, alias="spellScrollLevel")

    class Settings:
        name = "items"  # Maps both source files into a single collection

    model_config = {
        "populate_by_name": True,
        "extra": "ignore"  # Allow unmapped fields to prevent seeding blockage
    }