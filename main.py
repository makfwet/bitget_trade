import asyncio

from config import logger
from utils.BitgetSymbolCache.BitgetSymbolCache import BitgetSymbolCache
from src.BitgetWs import BitgetWS


async def main():
    FUNC_NAME = "MAIN"

    while True:
        logger.debug(f"[{FUNC_NAME}] Запускаю скрипт из цикла")

        try:
            await BitgetWS().start_bitget()

        except Exception as e:
            logger.critical(f"[{FUNC_NAME}] Неизвестная ошибка - {e}")



    #
    # trader = BitgetTrader(cache)
    #
    # await trader.open_position("ZKPUSDT", "buy", 50)
    #
    # await asyncio.Event().wait()

asyncio.run(main())
