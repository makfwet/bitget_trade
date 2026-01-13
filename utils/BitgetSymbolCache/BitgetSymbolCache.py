import asyncio
from time import time

from loguru import logger
from aiohttp import ClientSession

from config import API_BASE_URL, CACHE_UPDATE_INTERVAL
from utils.BitgetSymbolCache.CachedSymbol import CachedSymbol


class BitgetSymbolCache:
    symbol_cache: dict[CachedSymbol] = {}
    last_update: float | None = None
    __symbol_lock: asyncio.Lock = asyncio.Lock()


    async def update_scheduler(self, update_interval: int = CACHE_UPDATE_INTERVAL) -> None:
        """ Метод для постоянного обновления кеша с котировками """
        await self._update_cache()
        while True:
            await asyncio.sleep(update_interval)
            await self._update_cache()


    async def _update_cache(self) -> None:
        """ Метод для обновления кэша """
        FUNC_NAME = "UPDATE_CACHE"

        logger.debug(f"[{FUNC_NAME}] Обновление символов Bitget...")

        try:
            async with ClientSession(base_url=API_BASE_URL) as session:
                instruments, prices = await asyncio.gather(*(
                    self._fetch_instruments(session), self._fetch_prices(session)
                ))
        except Exception as e:
            logger.error(f"[{FUNC_NAME}] Ошибка при работе с сессией: {e}")

        if not instruments or not prices:
            logger.error(f"[{FUNC_NAME}] Не удалось обновить кэш")
            return

        # Собираем price_map
        price_map: dict[str, float] = {}
        cache = {}

        for item in prices:
            # Bitget v2 может использовать symbol ИЛИ instId
            if not (key := item.get("symbol") or item.get("instId")):
                continue

            try:
                price_map[key] = float(item.get("lastPr"))
            except:
                continue

        for item in instruments:
            if (symbol := item.get("symbol")) and (price := price_map.get(symbol)):
                try:
                    cache[symbol] = CachedSymbol(
                        price,
                        float(item["minTradeNum"]),
                        float(item["sizeMultiplier"])
                    )
                except:
                    continue

        async with self.__symbol_lock:
            self.symbol_cache = cache
            self.last_update = time()
        logger.success(f"[{FUNC_NAME}] Кэш обновлён: {len(self.symbol_cache)} символов")


    async def _fetch_instruments(self, session: ClientSession) -> list[dict[str, ...] | None]:
        """ Метод для получения торгуемых символов на Bitget """
        FUNC_NAME = "FETCH_INSTRUMENTS"

        try:
            async with session.get(
                "/api/v2/mix/market/contracts",
                params={"productType": "USDT-FUTURES"},
            ) as res:
                data = (await res.json()).get("data")

                if isinstance(data, dict):
                    return data.get("list", [])

                if isinstance(data, list):
                    return data

        except Exception as e:
            logger.error(f"[{FUNC_NAME}] Ошибка сетевого запроса: {e}")
        return []


    async def _fetch_prices(self, session: ClientSession) -> list[dict[str, ...] | None]:
        """ Метод для получения актуальных котировок цен на Bitget """
        FUNC_NAME = "FETCH_PRICES"

        try:
            async with session.get(
                "/api/v2/mix/market/tickers",
                params={"productType": "USDT-FUTURES"},
            ) as res:
                data = (await res.json()).get("data")

                if isinstance(data, dict):
                    return data.get("list", [])

                if isinstance(data, list):
                    return data

        except Exception as e:
            logger.error(f"[{FUNC_NAME}] Ошибка сетевого запроса: {e}")
        return []


    async def get_from_cache(self, symbol: str) -> CachedSymbol | None:
        """ Метод для получения символа из кэша """
        async with self.__symbol_lock:
            return self.symbol_cache.get(symbol.upper())


    def __del__(self) -> None:
        logger.debug("[DELETE] Объект bitget кэша удалён")