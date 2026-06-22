from beanie import Document
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Any, Optional

class AdventureRootBlueprint(Document):
    """
    The master blueprint compiled during Pass 3.
    Acts as the immutable schema template for module instantiation.
    """
    adventure_id: str = Field(description="Unique snake_case grouping token matching your NodeDTO records.")
    module_name: str = Field(description="Clean, user-facing title used to build Discord dropdown selects.")
    
    # Session Lifecylce Fields
    starting_node_id: str = Field(description="The structural entry room where players spawn on day one.")
    initiator_prompt: str = Field(description="Cinematic introductory text used by the parser to anchor player context.")
    
    default_npc_dispositions: Dict[str, str] = Field(
        default_factory=dict,
        description="Pre-seeded default stance mappings (e.g., {'klarg_the_bugbear': 'HOSTILE'}) to populate Session Delta ledger."
    )
    
    initial_story_flags: Dict[str, bool] = Field(
        default_factory=dict,
        description="Master global switches (e.g., {'sildar_rescued': False, 'supply_wagon_delivered': False}) to initialize state machines."
    )
    
    master_quest_registry: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="The complete baseline array of campaign tasks, tracking structural prerequisites and rewards."
    )

    model_config = ConfigDict(
        extra='forbid'
    )

    class Settings:
        name = "adventure_blueprints" # Explicit collection name