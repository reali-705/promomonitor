import asyncio
import logging
import sys

from telethon.errors import RPCError

from promomonitor.bot import client

logging.basicConfig(
    format="%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def _run_bot() -> None:
    """Orquestra a conexão MTProto e trava a thread no loop de eventos."""
    logger.info("Iniciando handshake com a rede do Telegram...")
    async with client:
        logger.info("Conexão estabelecida. O PromoMonitor está em escuta passiva.")
        await client.run_until_disconnected()  # pyright: ignore[reportGeneralTypeIssues]


def cli() -> None:
    """
    Entrypoint síncrono exigido pelo [project.scripts] no pyproject.toml.
    Encapsula o event loop e aplica redução de danos no desligamento (SIGINT).
    """
    try:
        asyncio.run(_run_bot())
    except KeyboardInterrupt:
        logger.info("Sinal de interrupção recebido. Desmontando a aplicação...")
    except (OSError, RPCError) as error:
        logger.exception("Falha de conexão com o Telegram.")
        raise SystemExit(1) from error


if __name__ == "__main__":
    cli()
