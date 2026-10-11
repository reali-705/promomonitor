import logging
from typing import Any, Protocol, TypeGuard, cast

from telethon import TelegramClient
from telethon.events import NewMessage

from promomonitor.bot.engine import MatchEngine
from promomonitor.bot.notifier import TelegramNotifier

logger = logging.getLogger(__name__)


class HasTitle(Protocol):
    title: str


def _is_chat_with_title(obj: Any) -> TypeGuard[HasTitle]:
    return hasattr(obj, "title") and isinstance(obj.title, str)


async def _extract_chat_metadata(event: NewMessage.Event) -> tuple[str, str]:
    raw_chat: Any = cast(Any, await event.get_chat())
    if _is_chat_with_title(raw_chat) and raw_chat.title.strip():
        chat_title = raw_chat.title.strip()
    else:
        chat_title = "Desconhecido"
    chat_id = cast(int | None, event.chat_id)  # pyright: ignore[reportUnknownMemberType]
    if isinstance(chat_id, int):
        clean_id = str(chat_id).removeprefix("-100")
        link = (
            f"https://t.me/c/{clean_id}/{event.id}"
            if event.is_channel
            else "Sem link (Grupo Privado)"
        )
    else:
        link = "Sem link"
    return chat_title, link


def _build_alert_message(
    matched_term: str,
    chat_title: str,
    link: str,
    price: float | None = None,
) -> str:
    if price is not None:
        price_str = (
            f"R$ {price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        )
    else:
        price_str = "Não encontrado"
    return (
        f"🚨 **PROMOÇÃO ENCONTRADA**\n\n"
        f"🔍 **Match:** `{matched_term}`\n"
        f"💰 **Preço:** {price_str}\n"
        f"📍 **Origem:** {chat_title}\n"
        f"🔗 **Link:** {link}"
    )


def register_handlers(
    client: TelegramClient,
    user_engines: dict[str, MatchEngine],
    notifier: TelegramNotifier,
) -> None:
    """Acopla o monitor MTProto de grupos ao mecanismo de despacho HTTP."""

    @client.on(NewMessage())
    async def monitor_handler(event: NewMessage.Event) -> None:
        # Ignora mensagens de conversas privadas
        if event.is_private or not event.raw_text:
            return

        text: str = event.raw_text
        chat_title: str | None = None
        link: str | None = None
        price: float | None = None

        for user_id, user_engine in user_engines.items():
            matched_term = user_engine.search(text)
            if not matched_term:
                continue

            if chat_title is None or link is None:
                chat_title, link = await _extract_chat_metadata(event)
                price = user_engine.extract_price(text)

            alert_payload = _build_alert_message(
                matched_term=matched_term,
                chat_title=chat_title,
                link=link,
                price=price,
            )
            await notifier.send_alert(
                chat_id=user_id,
                message=alert_payload,
            )
