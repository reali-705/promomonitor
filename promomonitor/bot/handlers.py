import logging
from typing import Any, Protocol, TypeGuard

from telethon import TelegramClient
from telethon.events import NewMessage

from promomonitor.bot.engine import MatchEngine
from promomonitor.storage import KeywordStorage

logger = logging.getLogger(__name__)


class HasTitle(Protocol):
    title: str


def _add(text: str, storage: KeywordStorage, engine: MatchEngine) -> str:
    payload = text.strip()
    if not payload:
        return "⚠️ Sintaxe incorreta. Uso: `/add termo1, termo2`"
    inserted, ignored = storage.add(payload)
    msg: list[str] = []
    if inserted:
        invalid_regex = engine.compile(storage.get_all())
        if invalid_regex:
            for invalid in invalid_regex:
                storage.remove(invalid)
                inserted.remove(invalid)
            msg.append(
                "❌ **ERRO DE REGEX:** Termos rejeitados pelo "
                f"compilador: {', '.join(invalid_regex)}"
            )
    if inserted:
        msg.append(f"✅ **Adicionados e Compilados:** `{', '.join(inserted)}`")
    if ignored:
        msg.append(f"🔄 **Ignorados (Já existiam):** `{', '.join(ignored)}`")

    return "\n".join(msg)


def _del(text: str, storage: KeywordStorage, engine: MatchEngine) -> str:
    term = text.strip()
    if not term:
        return "⚠️ Sintaxe incorreta. Uso: `/del termo`"
    if storage.remove(term):
        engine.compile(storage.get_all())
        return f"🗑️ **Removido:** `{term}` (Motor recompilado)"
    else:
        return f"⚠️ Termo não encontrado no cache: `{term}`"


def _list(storage: KeywordStorage) -> str:
    terms = storage.get_all()
    if not terms:
        return "📭 Banco de palavras-chave vazio."
    formatted_terms = "\n".join(f"• `{t}`" for t in sorted(terms))
    return f"📋 **Monitoramento Ativo ({len(terms)}):**\n{formatted_terms}"


def _help() -> str:
    return (
        "⚙️ **PromoMonitor CLI**\n\n"
        "`/add termo1, termo2` - Insere e compila novos padrões\n"
        "`/del termo` - Remove do banco e da memória\n"
        "`/list` - Exibe a árvore atual\n"
        "`/help` - Este menu"
    )


def _is_chat_with_title(obj: Any) -> TypeGuard[HasTitle]:
    """
    Inspeciona a memória em runtime. Se retornar True, o Pyright
    promove (narrows) silenciosamente o tipo 'Any' para 'HasTitle'.
    """
    return hasattr(obj, "title") and isinstance(obj.title, str)


# 3. A Função Unificada (1 I/O apenas)
async def _extract_chat_metadata(event: NewMessage.Event) -> tuple[str, str]:
    """
    Extrai título e link executando I/O apenas uma vez e calculando
    os IDs em O(1) na memória.
    """
    raw_chat: Any = await event.get_chat()
    if _is_chat_with_title(raw_chat) and raw_chat.title.strip():
        chat_title = raw_chat.title.strip()
    else:
        chat_title = "Desconhecido"
    chat_id = event.chat_id
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
    snippet: str,
    price: float | None = None,
) -> str:
    """
    Constrói a mensagem de alerta formatada para envio.
    """
    price_str = f"R$ {price:.2f}" if price is not None else "Não encontrado"
    return (
        f"🚨 **MATCH:** `{matched_term}`\n"
        f"💰 **Preço:** {price_str}\n"
        f"📍 **Origem:** {chat_title}\n"
        f"🔗 **Link:** {link}\n\n"
        f"📝 **Snippet:**\n{snippet[:300]}..."
    )


def register_handlers(
    client: TelegramClient,
    storage: KeywordStorage,
    engine: MatchEngine,
) -> None:
    """
    Acopla os handlers de evento da rede aos motores de estado e busca.
    """

    @client.on(NewMessage(chats="me", outgoing=True))
    async def command_handler(event: NewMessage.Event) -> None:
        text = event.raw_text.strip()
        if not text.startswith("/"):
            return
        command, context = text.split(" ", 1) if " " in text else (text, "")
        match command:
            case "/add":
                await event.respond(_add(context, storage, engine))
            case "/del":
                await event.respond(_del(context, storage, engine))
            case "/list":
                await event.respond(_list(storage))
            case "/help":
                await event.respond(_help())
            case _:
                await event.respond("⚠️ Comando desconhecido.\n" + _help())

    @client.on(NewMessage())
    async def monitor_handler(event: NewMessage.Event) -> None:
        if event.is_private or not event.raw_text:
            return
        text: str = event.raw_text
        matched_term = engine.search(text)
        if not matched_term:
            return
        chat_title, link = await _extract_chat_metadata(event)
        alert_payload = _build_alert_message(
            matched_term=matched_term,
            chat_title=chat_title,
            link=link,
            snippet=text,
            price=engine.extract_price(text),
        )
        await client.send_message("me", alert_payload)
