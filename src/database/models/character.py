from datetime import datetime
from enum import Enum
from beanie import Document, Indexed
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Annotated, Literal

# ==========================================
# 1. ENUMS & CORE TAXONOMY
# ==========================================

class ConditionType(str, Enum):
    BLINDED = "BLINDED"
    CHARMED = "CHARMED"
    DEAFENED = "DEAFENED"
    FRIGHTENED = "FRIGHTENED"
    GRAPPLED = "GRAPPLED"
    INCAPACITATED = "INCAPACITATED"
    INVISIBLE = "INVISIBLE"
    PARALYZED = "PARALYZED"
    PETRIFIED = "PETRIFIED"
    POISONED = "POISONED"
    PRONE = "PRONE"
    RESTRAINED = "RESTRAINED"
    STUNNED = "STUNNED"
    UNCONSCIOUS = "UNCONSCIOUS"

class ProficiencyTier(str, Enum):
    NONE = "NONE"
    HALF = "HALF"        # Bard's Jack of All Trades
    PROFICIENT = "PROFICIENT"
    EXPERTISE = "EXPERTISE"  # Rogue/Bard double proficiency bonus

# ==========================================
# 2. SUB-MODELS FOR VOLATILE RESOURCES
# ==========================================

class ActionEconomy(BaseModel):
    action_used: bool = Field(default=False, description="Tracks if the character has used their main action this round.")
    bonus_action_used: bool = Field(default=False, description="Tracks if the character has used their bonus action this round.")
    reaction_used: bool = Field(default=False, description="Tracks if the character has used their reaction. Resets at the start of their turn.")
    movement_spent_ft: int = Field(default=0, description="Tracks how many feet of movement the character has already spent this turn.")

class ResourcePool(BaseModel):
    current_hp: int = Field(description="Active health pool. Cannot drop below 0 or exceed max_hp.")
    temporary_hp: int = Field(default=0, description="Buffer health points consumed before current_hp.")
    exhaustion_level: int = Field(default=0, ge=0, le=6, description="Exhaustion stage (0-6). At 6, character dies.")
    death_saves_success: int = Field(default=0, ge=0, le=3, description="Successes when dying (0-3).")
    death_saves_failure: int = Field(default=0, ge=0, le=3, description="Failures when dying (0-3).")
    
    # Real-time round economy budget
    action_economy: ActionEconomy = Field(default_factory=ActionEconomy)
    custom_pools: Dict[str, int] = Field(
        default_factory=dict, 
        description="Tracks class-specific limited resources (e.g., {'sorcery_points': 4, 'superiority_dice': 3})."
    )

# ==========================================
# 3. CLASS & ATTRIBUTE REFERENCES
# ==========================================

class ClassProgression(BaseModel):
    class_name: str = Field(description="The generic name of the class (e.g., 'Paladin', 'Sorcerer').")
    subclass_name: Optional[str] = Field(default=None, description="The chosen archetype or subclass (e.g., 'Devotion').")
    levels: int = Field(default=1, ge=1, le=20, description="The number of levels invested into this specific class.")
    caster_type: Literal["FULL", "HALF", "THIRD", "NONE"] = Field(
        default="NONE", 
        description="Dictates spell slot weight math calculation for multi-classing setups."
    )

class AttributeScore(BaseModel):
    score: int = Field(description="The raw attribute integer score (e.g., 15).")
    
    @property
    def modifier(self) -> int:
        return (self.score - 10) // 2

class CharacterAttributes(BaseModel):
    str: AttributeScore
    dex: AttributeScore
    con: AttributeScore
    int: AttributeScore
    wis: AttributeScore
    cha: AttributeScore

# ==========================================
# 4. INVENTORY & EQUIPMENT TAXONOMY
# ==========================================

class Item(BaseModel):
    item_id: str = Field(description="Snake_case global identifier referencing the item master catalog (e.g., 'longsword_plus_1').")
    name: str = Field(description="The clear user-facing display string of the item.")
    quantity: int = Field(default=1, ge=1)
    weight_lbs: float = Field(default=0.0)
    is_equipped: bool = Field(default=False, description="True if armor is being worn or a weapon is wielded.")
    requires_attunement: bool = Field(default=False)
    is_attuned: bool = Field(default=False, description="True if the character is actively using one of their 3 attunement slots on this item.")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Custom modifiers, damage expressions, or ammo trackers.")

class SpellSlotTier(BaseModel):
    max: int = Field(default=0, description="Total spell slots available after a long rest.")
    used: int = Field(default=0, description="Active slots expended during the session.")

class SpellSlotTracker(BaseModel):
    level_1: SpellSlotTier = Field(default_factory=SpellSlotTier)
    level_2: SpellSlotTier = Field(default_factory=SpellSlotTier)
    level_3: SpellSlotTier = Field(default_factory=SpellSlotTier)
    level_4: SpellSlotTier = Field(default_factory=SpellSlotTier)
    level_5: SpellSlotTier = Field(default_factory=SpellSlotTier)
    level_6: SpellSlotTier = Field(default_factory=SpellSlotTier)
    level_7: SpellSlotTier = Field(default_factory=SpellSlotTier)
    level_8: SpellSlotTier = Field(default_factory=SpellSlotTier)
    level_9: SpellSlotTier = Field(default_factory=SpellSlotTier)

# ==========================================
# 5. THE ULTIMATE BEANIE CHARACTER DOCUMENT
# ==========================================

class CharacterSheet(Document):
    user_id: Annotated[str, Indexed()] = Field(description="The Discord User ID string mapping ownership of this character asset.")
    name: str = Field(description="The character name displayed in sheets and channel embeds.")
    
    # Structural Class Progression Arrays (Fixes multi-classing bugs)
    classes: List[ClassProgression] = Field(default_factory=list, description="Matrix of invested classes.")
    race: str
    background: str
    alignment: str
    experience_points: int = 0
    
    # Core Statistics
    attributes: CharacterAttributes
    base_armor_class: int = Field(description="The static baseline AC calculation derived from equipped armor items.")
    speed_ft_base: int = Field(default=30, description="The foundational native movement budget per round.")
    
    # Resource Pools and Status States
    resources: ResourcePool
    status_conditions: List[ConditionType] = Field(default_factory=list)
    
    # Granular Skill Maps (Fixes string list expertise bugs)
    saving_throw_proficiencies: Dict[str, ProficiencyTier] = Field(
        default_factory=dict, 
        description="e.g., {'str': 'PROFICIENT', 'con': 'NONE'}"
    )
    skill_proficiencies: Dict[str, ProficiencyTier] = Field(
        default_factory=dict, 
        description="e.g., {'stealth': 'EXPERTISE', 'perception': 'PROFICIENT', 'athletics': 'NONE'}"
    )
    tool_proficiencies: List[str] = Field(default_factory=list)
    
    # Features, Equipment & Spells
    features_and_traits: Dict[str, str] = Field(default_factory=dict)
    inventory: List[Item] = Field(default_factory=list)
    gold_pieces: int = 0
    
    known_spells: List[str] = Field(default_factory=list, description="List of spell snake_case reference catalog IDs.")
    spell_slots: SpellSlotTracker = Field(default_factory=SpellSlotTracker)
    
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # ==========================================
    # 6. ENGINE LIVE COMPUTATION PROPERTIES
    # ==========================================
    
    @property
    def level(self) -> int:
        """Dynamically scales global character level across multi-classes."""
        return sum(c.levels for c in self.classes)

    @property
    def proficiency_bonus(self) -> int:
        """Calculates standard 5e Proficiency Bonus curve deterministically."""
        return 2 + ((self.level - 1) // 4)

    @property
    def effective_caster_level(self) -> int:
        """Calculates correct caster level matrix to cross-reference multi-class slot charts."""
        total = 0
        for c in self.classes:
            if c.caster_type == "FULL":
                total += c.levels
            elif c.caster_type == "HALF":
                total += c.levels // 2
            elif c.caster_type == "THIRD":
                total += c.levels // 3
        return max(1, total)

    @property
    def total_weight_carried(self) -> float:
        """Calculates live structural inventory weight burdens."""
        item_weight = sum(i.weight_lbs * i.quantity for i in self.inventory)
        coin_weight = self.gold_pieces * 0.02 # Standard 50 coins to a pound rule
        return round(item_weight + coin_weight, 2)

    @property
    def is_encumbered(self) -> bool:
        """Enforces strength capacity thresholds directly."""
        return self.total_weight_carried > (self.attributes.str.score * 5)

    class Settings:
        name = "characters"