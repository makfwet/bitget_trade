import asyncio
from time import time
from typing import Literal
from json import dumps, loads, JSONDecodeError

from loguru import logger
from websockets.exceptions import ConnectionClosedError
from websockets.asyncio.client import connect, ClientConnection

from config import (
    WS_BASE_URL,
    PING_INTERVAL,
    BITGET_API_KEY,
    BITGET_API_PASSPHRASE,
    TRADE_USDT,
    RECONNECT_INTERVAL,
)
from utils.BitgetSymbolCache import BitgetSymbolCache
from utils.instruments import generate_sign, calc_qty, generate_order_id


class BitgetWS:
    ws: ClientConnection | None = None
    ws_connected: bool = False
    ws_ping_task: asyncio.Task | None = None
    symbol_cache: BitgetSymbolCache = BitgetSymbolCache()
    update_cache_task: asyncio.Task | None = None


    async def _connect(self) -> bool:
        """ Метод для установки websocket-соединения с Bitget """
        FUNC_NAME = "CONNECT"

        try:
            self.ws = await connect(WS_BASE_URL, ping_interval=None)
        except Exception as e:
             logger.error(f"[{FUNC_NAME}] Ошибка подключения: {e}")
             return False

        res = await self._login()
        if res == "Success":
            pass
        elif res == "ConnectionClosedError":
            logger.error(f"[{FUNC_NAME}] Ошибка подключения: неудачный логин")
            self.ws, self.ws_connected = None, False
            return False
        else:
            logger.error(f"[{FUNC_NAME}] Ошибка подключения: {res}")
            self.ws, self.ws_connected = None, False
            return False

        self.ws_connected = True
        self.ws_ping_task = asyncio.create_task(self._ping())
        logger.success(f"[{FUNC_NAME}] Соединение с Bitget установлено!")
        return True


    async def _login(self) -> Literal["Success", "ConnectionClosedError"] | str:
        """
        Метод для авторизации на сервере Bitget.

        Возвращает:
            * Success - как успешный ответ (код == 0)
            * ConnectionClosedError - при разрыве websocket-соединения
            * Строку с описанием ошибки - как неудачный ответ (код != 0)
        """
        timestamp = int(time())
        msg = {
            "op": "login",
            "args": [{
                "apiKey": BITGET_API_KEY,
                "passphrase": BITGET_API_PASSPHRASE,
                "timestamp": timestamp,
                "sign": generate_sign(timestamp, "GET", "/user/verify"),
            }]
        }

        try:
            await self.ws.send(dumps(msg))
            res = loads(await self.ws.recv())
        except ConnectionClosedError:
            return "ConnectionClosedError"

        return "Success" if res.get("code") == 0 else res.get("msg")


    async def _ping(self, ping_interval: int = PING_INTERVAL) -> None:
        """ Метод таска для пинга. Отправляет ping раз в ping_interval секунд"""
        FUNC_NAME = "PING"

        while self.ws and self.ws_connected:
            await asyncio.sleep(ping_interval)
            try:
                pong_latency = await (await self.ws.ping())
                logger.debug(f"[{FUNC_NAME}] Пинг-понг, задержка {pong_latency:.2f}с")

            except ConnectionClosedError:
                self.ws, self.ws_connected = None, False
                logger.warning(f"[{FUNC_NAME}] Соединение потеряно")

            except Exception as e:
                self.ws, self.ws_connected = None, False
                logger.error(f"[{FUNC_NAME}] Ошибка: {e}")


    async def _send_json(self, payload: dict) -> None:
        """ Метод для отправки сообщения на сервер """
        FUNC_NAME = "SEND_JSON"

        if not self.ws or not self.ws_connected:
            logger.warning(f"[{FUNC_NAME}] Соединение потеряно")
            return

        try:
            await self.ws.send(dumps(payload))
        except Exception as e:
            logger.error(f"[{FUNC_NAME}] Неизвестная ошибка при отправке сообщения: {e}")


    async def _listen(self) -> None:
        """ Метод для прослушки входящих сообщений от Bitget """
        FUNC_NAME = "LISTEN"

        async for msg in self.ws:
            try:
                msg = loads(msg)
            except JSONDecodeError:
                continue

            if msg.get("event") == "error":
                logger.error(f"[{FUNC_NAME}] {msg}")
            else:
                logger.info(f"[{FUNC_NAME}] {msg}")


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

            tasks.append(self._create_order(symbol, side, qty))

        if tasks:
            await asyncio.gather(*tasks)
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

        if not self.ws or not self.ws_connected:
            logger.error(f"[{FUNC_NAME}] Нет подключения! Ордер не отправлен: {symbol} {side} {qty}")
            return

        msg = {
            "args":[{
                "channel": "place-order",
                "id": generate_order_id(),
                "instId": symbol,
                "instType": "USDT-FUTURES",
                "params": {
                    "orderType": "market",
                    "side": side.lower(),
                    "size": "2",
                    "marginCoin": "USDT",
                    "force": "ioc",
                    "marginMode": "crossed",
                }
            }],
            "op": "trade"
        }

        await self._send_json(msg)
        logger.info(f"[{FUNC_NAME}] Отправил ордер: {msg}")


    async def test_task(self, time: int) -> None:
        """
        ТЕСТОВЫЙ МЕТОД!
        Метод для имитации поступления данных для трейда от парсера.
        Запускается один раз через time секунд
        """

        await asyncio.sleep(time)
        print(await self.prepare_to_trade(('Buy', {'NIGHTUSDT'})))


    async def start_bitget(self) -> None:
        """ Метод для начала установки соединения с Bitget. Точка входа """
        FUNC_NAME = "START_BITGET"

        while True:
            if not await self._connect():
                if self.update_cache_task:
                    self.update_cache_task.cancel()

                logger.warning(f"[{FUNC_NAME}] Соединение разорвано или не было установлено! Повтор через {RECONNECT_INTERVAL} сек...")
                await asyncio.sleep(RECONNECT_INTERVAL)
                continue

            self.update_cache_task = asyncio.create_task(self.symbol_cache.update_scheduler())
            await self._listen()


    def __del__(self) -> None:
        if self.update_cache_task:
            self.update_cache_task.cancel()
        logger.debug("[DELETE] Объект торгового bitget-сокета удалён")