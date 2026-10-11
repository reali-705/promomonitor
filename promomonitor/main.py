import asyncio
import logging
import sys

from telethon.errors import RPCError

from promomonitor.bot import client, notifier, storage, user_engines

logging.basicConfig(
    format="%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def _run_bot() -> None:
    logger.info("Iniciando handshake com a rede do Telegram...")
    try:
        async with client:
            logger.info("Conexão estabelecida. O PromoMonitor está em escuta passiva.")
            # Executa a escuta do MTProto e o Polling HTTP concorrentemente
            await asyncio.gather(
                client.run_until_disconnected(),  # pyright: ignore[reportArgumentType]
                notifier.start_polling(storage, user_engines),
            )  # type: ignore
    finally:
        # Garante o fechamento limpo das conexões HTTP
        await notifier.close()


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
