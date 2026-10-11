import logging

from telethon import TelegramClient

from promomonitor.bot.engine import MatchEngine
from promomonitor.bot.handlers import register_handlers
from promomonitor.bot.notifier import TelegramNotifier
from promomonitor.config import get_settings
from promomonitor.storage import KeywordStorage

logger = logging.getLogger(__name__)

settings = get_settings()
storage = KeywordStorage(settings.STORAGE_PATH)
notifier = TelegramNotifier(settings.BOT_TOKEN)

# Inicializa e compila os motores por usuário
user_engines: dict[str, MatchEngine] = {}
for user_id, terms in storage.get_all_users().items():
    engine = MatchEngine()
    invalid_terms = engine.compile(terms)
    if invalid_terms:
        logger.warning(
            "Usuário %s possui padrões corrompidos: %s",
            user_id,
            invalid_terms,
        )
    user_engines[user_id] = engine

client = TelegramClient(
    settings.SESSION_NAME,
    settings.API_ID,
    settings.API_HASH,
)

register_handlers(
    client=client,
    user_engines=user_engines,
    notifier=notifier,
)

__all__ = ["client", "notifier", "storage", "user_engines"]
