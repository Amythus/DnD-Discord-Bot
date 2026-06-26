# root/src/database/models/__init__.py
from .config.channel import ChannelConfig
from .static.monster import Monster
from .static.spell import Spell
from .static.item import Item
# from .session.session import CampaignSession
from .session.delta import SessionDelta
from .identity.character import Character
from .identity.registry import PlayerRegistry
from .campaign.adventure_blueprint import AdventureBlueprint
from .campaign.adventure_node import GameNode
# from .llm.cache import RulebookCacheMetadata

# Export this list to database/connection.py for beanie.init_beanie()
__all_models__ = [
    AdventureBlueprint,
    ChannelConfig,
    Monster,
    Spell,
    Item,
    GameNode,
    # CampaignSession,
    SessionDelta,
    Character,
    PlayerRegistry,
    # RulebookCacheMetadata
]