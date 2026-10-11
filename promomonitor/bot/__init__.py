import logging

from telethon import TelegramClient

from promomonitor.bot.engine import MatchEngine
from promomonitor.bot.handlers import register_handlers
from promomonitor.config import get_settings
from promomonitor.storage import KeywordStorage

logger = logging.getLogger(__name__)


settings = get_settings()
storage = KeywordStorage(settings.STORAGE_PATH)
engine = MatchEngine()

invalid_terms = engine.compile(storage.get_all())

if invalid_terms:
    logger.warning(
        "Expurgando %d padrões corrompidos encontrados no boot: %s",
        len(invalid_terms),
        invalid_terms,
    )

client = TelegramClient(
    settings.SESSION_NAME,
    settings.API_ID,
    settings.API_HASH,
)

register_handlers(client, storage, engine)

__all__ = ["client"]
