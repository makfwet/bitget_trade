import asyncio

from config import logger
from src.BitgetWs import BitgetWS


async def main():
    FUNC_NAME = "MAIN"

    while True:
        logger.debug(f"[{FUNC_NAME}] Запускаю скрипт из цикла")

        try:
            bitget_client = BitgetWS()
            await bitget_client.start_bitget()

        except Exception as e:
            logger.critical(f"[{FUNC_NAME}] Неизвестная ошибка: {e}")


if __name__ == "__main__":
    asyncio.run(main())