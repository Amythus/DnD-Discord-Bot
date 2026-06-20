from typing import List, Optional
from uuid import UUID
from beanie import Document, Indexed
from pydantic import HttpUrl, Field

class CharacterRegistry(Document):
    """
    The relational mapper for account-level identity linking.
    Stitches Discord identities, D&D Beyond URIs, local Character records,
    and Campaign permissions together.
    """
    # The absolute unique identifier for the player on Discord.
    # Indexed uniquely because this is the lookup key for every message event.
    discord_user_id: Indexed(int, unique=True)
    
    # The unique UUID of the character currently loaded/selected by the player.
    # References the `character_id` field inside the identity_characters collection.
    active_character_id: Optional[UUID] = None
    
    # D&D Beyond Sync integration mappings
    # Stores the profile/character tracking URL for downstream API scrapers or proxies
    dndb_uri: Optional[HttpUrl] = None
    # Alternatively stored as a numerical token ID string extracted from the D&DB payload
    dndb_character_id: Optional[str] = None
    
    # Whitelist array tracking which active CampaignSessions this user has permission to join.
    # When a player attempts to run a session interaction, the engine verifies 
    # that the channel's `active_session_id` exists inside this list.
    joined_session_ids: List[UUID] = Field(default_factory=list)

    class Settings:
        name = "identity_registry"  # Collection name inside MongoDB

    class Config:
        json_schema_extra = {
            "example": {
                "discord_user_id": 123456789012345678,
                "active_character_id": "550e8400-e29b-41d4-a716-446655440000",
                "dndb_uri": "https://character-service.dndbeyond.com/character/v5/character/109283451",
                "dndb_character_id": "109283451",
                "joined_session_ids": [
                    "123e4567-e89b-12d3-a456-426614174000",
                    "987f6543-b21a-34c5-d678-987654321000"
                ]
            }
        }