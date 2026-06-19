# root/src/database/models/__init__.py
from .config.channel import ChannelConfig
# from .static.monster import Monster
# from .static.spell import Spell
# from .static.item import Item
# from .spatial.node import MapNode
from .session.session import CampaignSession
from .session.delta import SessionDelta
from .identity.character import Character
from .identity.registry import CharacterRegistry
# from .llm.cache import RulebookCacheMetadata

# Export this list to database/connection.py for beanie.init_beanie()
__all_models__ = [
    ChannelConfig,
    # Monster,
    # Spell,
    # Item,
    # MapNode,
    CampaignSession,
    SessionDelta,
    Character,
    CharacterRegistry,
    # RulebookCacheMetadata
]