from beanie import Document
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import List, Dict, Any, Optional
# Mirror shared baseline blocks natively from node structures
from database.models.campaign.adventure_node import FactionDisposition, ExecutionEffect

# =====================================================================
# CAMPAIGN INFRASTRUCTURE SUB-MODELS
# =====================================================================

class GlobalBehaviorTrigger(BaseModel):
    """
    Captures module-wide conditional interactions evaluating rules 
    and overriding localized room configurations globally.
    """
    global_trigger_id: str = Field(
        description="Unique snake_case tracking string representing this macro conditional interaction loop."
    )
    conditions: List[str] = Field(
        default_factory=list,
        description="A list of evaluate-ready conditional parameters required to execute this event block."
    )
    execution_effects: List[ExecutionEffect] = Field(
        default_factory=list,
        description="The structured list of technical state alterations pushed globally when conditions resolve to true."
    )

class MasterQuestRegistryItem(BaseModel):
    """
    Defines a structural quest ledger entry instantiated at the module level.
    """
    quest_id: str = Field(description="Unique lookup tracking token for this storyline node.")
    name: str = Field(description="Clean, user-facing presentation header printed to player quest lists.")
    prerequisites: List[str] = Field(
        default_factory=list, 
        description="List of global story flag keys required to initialize this tracking thread."
    )
    objectives: List[str] = Field(description="Concrete linear narrative progression conditions players must satisfy.")
    rewards: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Dynamic structural modifications or item rewards granted upon quest resolution."
    )

# =====================================================================
# PERSISTENT BEANIE ODM DATABASE DOCUMENT MODEL
# =====================================================================

class AdventureBlueprint(Document):
    """
    The master immutable orchestrator layout blueprint document.
    Serves as the core data template tracking initialized campaign states.
    """
    adventure_id: str = Field(
        description="Unique snake_case campaign identifier matching your relational GameNode records."
    )
    module_name: str = Field(
        description="Clean presentation header string used to build Discord configurations and drop-down selectors."
    )
    starting_node_id: str = Field(
        description="The initial entry spatial node identification key indicating where players spawn on game initialization."
    )
    
    # Fully Decoupled Orchestration Instructions
    initiator_prompt: str = Field(
        description="Systemic instruction infrastructure used to frame layout settings and rule interpretations for AI routers."
    )
    story_hook: str = Field(
        description="Narrative player-facing description or text printed straight into Discord channel webhooks on initialization."
    )
    
    # Thread Pools with Thread-Safe Lambda Factories
    default_npc_dispositions: Dict[str, FactionDisposition] = Field(
        default_factory=lambda: {},
        description="Default faction alignment maps (e.g., {'baron_uthrak_thugs': 'HOSTILE'}) seeding active session parameters."
    )
    initial_story_flags: Dict[str, bool] = Field(
        default_factory=lambda: {},
        description="Master initial state switches tracking global structural events initialized to False."
    )
    master_quest_registry: List[MasterQuestRegistryItem] = Field(
        default_factory=lambda: [],
        description="The complete list of quest tracking configurations outlining milestones and validation requirements."
    )
    global_behavior_triggers: List[GlobalBehaviorTrigger] = Field(
        default_factory=lambda: [],
        description="Adventure-wide interaction rule modifiers parsed consistently across every node traversal step."
    )

    model_config = ConfigDict(
        extra='forbid',
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "adventure_id": "burnock_mill",
                "module_name": "The Mystery of Burnock Mill",
                "starting_node_id": "truss_bridge_u1",
                "initiator_prompt": "An atmospheric, gritty campaign taking place in a rain-slicked valley topologyl...",
                "story_hook": "The party arrives at the muddy bank of the Burnock River, finding an old mill looming in the fog...",
                "default_npc_dispositions": {
                    "baron_uthrak_forces": "HOSTILE"
                },
                "initial_story_flags": {
                    "valley_on_high_alert": False
                },
                "master_quest_registry": [
                    {
                        "quest_id": "expose_the_baron",
                        "name": "Exposing the Baron",
                        "prerequisites": [],
                        "objectives": ["Find evidence of the toll extortion rackets", "Confront the mill master"],
                        "rewards": {"party_reputation": 5}
                    }
                ],
                "global_behavior_triggers": [
                    {
                        "global_trigger_id": "uthrak_bounty_alert",
                        "conditions": ["party_kills_bridge_bandits == true"],
                        "execution_effects": [
                            {
                                "effect_target": "global_state.threat_level",
                                "set_value": "HIGH"
                            }
                        ]
                    }
                ]
            }
        }
    )

    @field_validator('default_npc_dispositions', mode='before')
    @classmethod
    def coerce_disposition_keys_uppercase(cls, v: Any) -> Any:
        if isinstance(v, dict):
            return {k: val.upper() if isinstance(val, str) else val for k, val in v.items()}
        return v

    class Settings:
        name = "adventure_blueprints"  # Explicit MongoDB database collection matching Phase 4 mapping operations