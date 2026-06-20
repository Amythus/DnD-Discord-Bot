from typing import Optional
from uuid import UUID
from beanie import Document, Indexed
from pydantic import Field
from pymongo import IndexModel, ASCENDING, DESCENDING


class ChannelConfig(Document):
    """
    Infrastructure mapping that bridges a specific Discord Channel 
    to a running game session. Acts as the entry-way routing engine.
    """
    # The Discord ID of the channel where the game is being played.
    # We index this because the Discord bot will query this collection
    # on almost every incoming message to check if it should parse it.
    channel_id: int
    
    # The ID of the Discord Guild/Server (useful for multi-tenant cleanup)
    guild_id: int
    
    # The UUID of the active CampaignSession running in this channel.
    # If None, no active game is currently running here.
    active_session_id: Optional[UUID] = None
    
    # Optional metadata: Tracking who started the session or holds DM rights here
    dm_discord_id: Optional[int] = None
    
    # A toggle to pause the bot from reading this channel without ending the session
    is_paused: bool = Field(default=False)

    # class Settings:
    #     name = "config_channels" # The name of the MongoDB collection

    #     indexes = [
    #         {
    #             "key": [("channel_id", 1)],
    #             "unique": True
    #         },
    #         "guild_id"
    #     ]

    class Settings:
        name = "config_channels" 
        
        indexes = [
            IndexModel([("channel_id", ASCENDING)], unique=True),
            "guild_id"
        ]


    class Config:
        schema_extra = {
            "example": {
                "channel_id": 10928374658293,
                "guild_id": 99887766554433,
                "active_session_id": "123e4567-e89b-12d3-a456-426614174000",
                "dm_discord_id": 445566778899,
                "is_paused": False
            }
        }

# When an admin runs /whitelist add, the bot creates (or updates) a ChannelConfig document for that channel_id