import asyncio
import logging
from typing import Any

import httpx

from promomonitor.bot.engine import MatchEngine
from promomonitor.storage import KeywordStorage

logger = logging.getLogger(__name__)

COMMANDS = (
    " - `/add rtx 4060, ryzen` - Adiciona múltiplos termos separados por vírgula\n"
    " - `/del rtx 4060` - Remove um termo\n"
    " - `/list` - Mostra todos os seus termos\n"
)


class TelegramNotifier:
    """
    Despachante e ouvinte HTTP (Bot API).
    Envia alertas com push/som e atende requisições de comandos dos usuários em segundo plano.
    """

    def __init__(self, bot_token: str) -> None:
        self._token = bot_token
        self._base_url = f"https://api.telegram.org/bot{bot_token}"
        self._client = httpx.AsyncClient(timeout=40.0)
        self._is_running = False

    async def send_alert(self, chat_id: str, message: str) -> bool:
        """Dispara mensagem direta para um chat_id."""
        url = f"{self._base_url}/sendMessage"
        payload: dict[str, str | int | bool] = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False,
        }
        try:
            response = await self._client.post(url, json=payload)
            if response.status_code != 200:
                logger.error(
                    "Falha ao notificar %s (HTTP %d): %s",
                    chat_id,
                    response.status_code,
                    response.text,
                )
                return False
            return True
        except httpx.HTTPError as exc:
            logger.error("Erro de transporte ao notificar %s: %s", chat_id, exc)
            return False

    async def _handle_command(
        self,
        chat_id: str,
        text: str,
        storage: KeywordStorage,
        user_engines: dict[str, MatchEngine],
    ) -> str:
        """Processa a intenção do usuário isolando pelo chat_id do remetente."""
        parts = text.strip().split(" ", 1)
        command = parts[0].lower()
        context = parts[1].strip() if len(parts) > 1 else ""

        match command:
            case "/start":
                return (
                    "👋 **Bem-vindo ao PromoMonitor!**\n\n"
                    "Eu monitoro ofertas em tempo real e te aviso assim que encontrar algo do seu interesse.\n\n"
                    "Comandos disponíveis:\n"
                    f"{COMMANDS}"
                )

            case "/add":
                if not context:
                    return "⚠️ Informe os termos para adicionar.\nExemplo: `/add rtx 4060, ryzen 5`"

                inserted, ignored = storage.add(chat_id, context)
                engine = user_engines.setdefault(chat_id, MatchEngine())
                invalid_regex = engine.compile(storage.get_user_terms(chat_id))

                res: list[str] = []
                if invalid_regex:
                    res.append(
                        f"❌ **Termos rejeitados (Regex inválido):** {', '.join(invalid_regex)}"
                    )
                if inserted:
                    res.append(f"✅ **Adicionados:** `{', '.join(inserted)}`")
                if ignored:
                    res.append(f"🔄 **Já cadastrados:** `{', '.join(ignored)}`")
                return "\n".join(res)

            case "/del":
                if not context:
                    return "⚠️ Informe o termo para remover.\nExemplo: `/del rtx 4060`"

                if storage.remove(chat_id, context):
                    if chat_id in user_engines:
                        user_engines[chat_id].compile(storage.get_user_terms(chat_id))
                    return f"🗑️ **Removido com sucesso:** `{context}`"
                return f"⚠️ Termo `{context}` não encontrado na sua lista."

            case "/list":
                terms = storage.get_user_terms(chat_id)
                if not terms:
                    return "📭 Você ainda não cadastrou nenhuma palavra-chave.\nUse `/add <termo>` para começar."

                terms_fmt = "\n".join(f" - `{t}`" for t in sorted(terms))
                return f"📋 **Seus termos monitorados ({len(terms)}):**\n{terms_fmt}"

            case "/help":
                return (
                    "⚙️ **PromoMonitor CLI**\n\n"
                    "Você não precisa digitar seu ID. Suas palavras-chave são totalmente individuais.\n\n"
                    f"{COMMANDS}"
                )

            case _:
                return (
                    "⚠️ Comando não reconhecido. Digite uma das opções abaixo.\n\n"
                    f"{COMMANDS}"
                )

    async def start_polling(
        self,
        storage: KeywordStorage,
        user_engines: dict[str, MatchEngine],
    ) -> None:
        """Loop de polling assíncrono para escutar mensagens direcionadas ao Bot."""
        self._is_running = True
        offset = 0
        url = f"{self._base_url}/getUpdates"
        logger.info("Mecanismo de autoatendimento HTTP do Bot iniciado.")

        while self._is_running:
            try:
                resp = await self._client.get(
                    url, params={"offset": offset, "timeout": 30}
                )
                if resp.status_code != 200:
                    await asyncio.sleep(3)
                    continue

                data: dict[str, Any] = resp.json()
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    message = update.get("message")
                    if not message or "text" not in message:
                        continue

                    chat_id = str(message["chat"]["id"])
                    text = message["text"].strip()

                    reply_text = await self._handle_command(
                        chat_id,
                        text,
                        storage,
                        user_engines,
                    )
                    await self.send_alert(chat_id, reply_text)

            except httpx.ReadTimeout:
                continue
            except httpx.HTTPError as exc:
                logger.warning(
                    "Falha de rede temporária no Polling: %s. Tentando novamente...",
                    exc,
                )
                await asyncio.sleep(5)
            except Exception:
                logger.exception("Erro inesperado no loop de updates do bot.")
                await asyncio.sleep(5)

    async def close(self) -> None:
        """Interrompe o polling e fecha conexões HTTP."""
        self._is_running = False
        await self._client.aclose()
