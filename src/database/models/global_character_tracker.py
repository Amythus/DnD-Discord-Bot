from beanie import Document, Indexed
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class GlobalTrackerCharacter(Document):
    """The permanent baseline database record for a character across all campaigns."""
    user_id: Indexed(str)  # The Discord User ID who owns this character
    character_name: str
    
    # External Sync Anchor for mid-week hydration
    dndbeyond_url: Optional[str] = None
    last_synced_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Pristine Core Specs fetched from D&D Beyond / 5e.tools baseline
    # These represent the character at full rest / 100% health
    max_hp: int
    hit_dice_total: int
    hit_dice_type: str  # e.g., "d8"
    level: int
    character_class_map: Dict[str, int] = Field(default_factory=dict)  # {"Warlock": 3, "Paladin": 2}
    
    # Permanent inventory or notes (independent of any single episodic campaign)
    base_equipment: List[str] = Field(default_factory=list)

    class Settings:
        name = "global_characters"