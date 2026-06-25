from typing import Optional
from pydantic import Field
from beanie import Document, Indexed

class AdventureBlueprint(Document):
    """
    The macro-parent orchestration document inside MongoDB representing a campaign module's root metadata.
    Acts as the source-of-truth configuration anchor that groups all underlying GameNodes together.
    Completely read-only during session runtime to maintain flawless caching layers.
    """
    adventure_id: Indexed(str, unique=True) = Field(
        ..., 
        description="Global unique snake_case identifier for the adventure module used to tie GameNodes together."
    )
    campaign_title: str = Field(
        ..., 
        description="Clean, user-facing name of the overarching campaign displayed onto the client UI."
    )
    
    # -----------------------------------------------------------------
    # AI vs Player Interface Boundaries
    # -----------------------------------------------------------------
    initiator_prompt: str = Field(
        ..., 
        description=(
            "AI-Facing Systemic Infrastructure Text. Acts as the foundational system instructions "
            "and environmental anchor to ground world-parsing logic boundaries for your routers."
        )
    )
    story_hook: str = Field(
        ..., 
        description=(
            "Player-Facing Narrative Infrastructure Text. The introductory 'flavor text' or back-of-the-book "
            "blurb printed directly to the Discord channel when a party initializes a session."
        )
    )
    
    # -----------------------------------------------------------------
    # Optional Structural Metadata Hooks
    # -----------------------------------------------------------------
    starting_node_id: str = Field(
        default="area_1_entrance",
        description="The entry snake_case node_id where players materialize when beginning the campaign."
    )
    version: str = Field(
        default="1.0.0",
        description="Tracking version string for the source markdown asset parser iteration."
    )

    class Settings:
        name = "adventure_blueprints"
        indexes = [
            "adventure_id",
            "campaign_title"
        ]