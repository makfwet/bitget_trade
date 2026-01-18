import asyncio
from time import time
from json import dumps
from typing import Literal

from loguru import logger
from aiohttp import ClientSession

from utils.BitgetSymbolCache import BitgetSymbolCache
from utils.instruments import calc_qty, generate_headers, response_prettifier
from config import API_BASE_URL, TRADE_USDT, RECONNECT_INTERVAL


class BitgetRest:
    funding_assets_endp = "/api/v2/account/funding-assets"
    place_order_endp: str = "/api/v2/mix/order/place-order"

    client: ClientSession | None = None
    symbol_cache: BitgetSymbolCache = BitgetSymbolCache()
    update_cache_task: asyncio.Task | None = None


    def __init__(self) -> None:
        self.update_cache_task = asyncio.create_task(self.symbol_cache.update_scheduler())


    async def _connect(self) -> bool:
        """ Метод для установки соединения с Bitget """
        FUNC_NAME = "CONNECT"

        try:
            self.client = ClientSession()
            if res := await self._funding_assets():
                logger.success(f"[{FUNC_NAME}] Соединение с Bitget установлено!")
                return True

        except Exception as e:
             logger.error(f"[{FUNC_NAME}] Ошибка подключения: {e}")
        return False


    async def _funding_assets(self) -> None | str:
        """ Отправка запроса для получения баланса """
        FUNC_NAME = "FUNDING_ASSETS"

        timestamp = int(time() * 1000)
        try:
            res = await self.client.get(
                API_BASE_URL + self.funding_assets_endp,
                headers=generate_headers(self.funding_assets_endp, timestamp, "GET")
            )
        except Exception as e:
            logger.error(f"[{FUNC_NAME}] Ошибка сетевого запроса: {e}")
            return

        return response_prettifier(timestamp, await res.json())


    async def _ping(self, ping_interval: int = 5) -> bool:
        """ Поллинг с методом funding_assets. Отправляет запрос раз в ping_interval секунд """
        FUNC_NAME = "PING"

        await asyncio.sleep(ping_interval)
        res_for_log = await self._funding_assets()

        if isinstance(res_for_log, tuple) and res_for_log[0] is True:
            logger.debug(f"[{FUNC_NAME}] [{res_for_log[1]}мс] Пинг отправлен")
        elif isinstance(res_for_log, tuple) and res_for_log[0] is False:
            logger.warning(f"[{FUNC_NAME}] [{res_for_log[1]}мс] Ошибка пинга")

        if not res_for_log:
            self.client = None
            return False
        return True


    async def prepare_to_trade(
        self,
        data_to_trade: tuple[Literal["Buy", "Sell"], set[str]]
    ) -> tuple[list[str], list[str]]:
        """
        Подготовка тасков для торговли.
        Возвращает пустой кортеж при успешном создании всех торговых тасок,
        при отсутствии токена в кэше вернет +1 символ в списке unlisted_symbols,
        при вычисленном qty ниже qty из кэша вернет +1 символ и микро лог в списке impossible_qty_symbols
        """

        side, symbols = data_to_trade
        tasks = []
        unlisted_symbols = []
        impossible_qty_symbols = []

        for symbol in symbols:
            if not (data := await self.symbol_cache.get_from_cache(symbol)):
                unlisted_symbols.append(symbol)
                continue

            qty = calc_qty(TRADE_USDT, data.price, data.qty_step)

            if qty < data.min_qty:
                impossible_qty_symbols.append((symbol, f'{qty}<{data.min_qty}'))
                continue

            tasks.append(asyncio.create_task(self._create_order(symbol, side, qty)))

        return unlisted_symbols, impossible_qty_symbols


    async def _create_order(
        self,
        symbol: str,
        side: Literal["Buy", "Sell"],
        qty: float,
        sleep_time: int = 60
    ) -> None:
        """ Отправка запроса на открытие ордера """
        FUNC_NAME = "CREATE_ORDER"

        if side == "Sell":
            logger.debug(f"[{FUNC_NAME}] Сплю {sleep_time}с: {symbol} {side} {qty}")
            await asyncio.sleep(sleep_time)

        if not self.client:
            logger.error(f"[{FUNC_NAME}] Нет подключения! Ордер не отправлен: {symbol} {side} {qty}")
            return

        timestamp = int(time()*1000)
        body = dumps({
            "symbol": symbol,
            "productType": "USDT-FUTURES",
            "marginMode": "crossed",
            "marginCoin": "USDT",
            "posMode": "one_way",
            "side": side.lower(),
            "orderType": "market",
            "tradeSide": "open",
            "size": qty,
        })

        try:
            async with self.client.post(
                API_BASE_URL + self.place_order_endp,
                data=body,
                headers=generate_headers(self.place_order_endp, timestamp, "POST", body),
            ) as res:
                res_for_log = response_prettifier(timestamp, await res.json())

                if isinstance(res_for_log, tuple) and res_for_log[0] is True:
                    logger.success(f"[{FUNC_NAME}] [{res_for_log[1]}мс] {symbol} {side} {qty} - Открыл позицию!")
                elif isinstance(res_for_log, tuple) and res_for_log[0] is False:
                    logger.warning(f"[{FUNC_NAME}] [{res_for_log[1]}мс] ({side} {symbol} {qty}) - Не удалось открыть ордер: {res_for_log[2]}")
                else:
                    logger.error(f"[{FUNC_NAME}] Не удалось получить корректный ответ от Bitget")

        except Exception as e:
            logger.error(f"[{FUNC_NAME}] Не удалось отправить ордер: {body} из-за ошибки: {e}")


    async def test_task(self, time: int) -> None:
        """
        ТЕСТОВЫЙ МЕТОД!
        Метод для имитации поступления данных для трейда от парсера.
        Запускается один раз через time секунд
        """

        await asyncio.sleep(time)
        print(await self.prepare_to_trade(('Buy', {'usdcUSDT'})))


    async def start_bitget(self) -> None:
        """ Метод для начала установки соединения с Bitget. Точка входа """
        FUNC_NAME = "START_BITGET"

        await self._connect()

        while True:
            if not await self._ping():
                logger.warning(f"[{FUNC_NAME}] Соединение разорвано или не было установлено! Повтор через {RECONNECT_INTERVAL} сек...")
                await asyncio.sleep(RECONNECT_INTERVAL)
                await self._connect()