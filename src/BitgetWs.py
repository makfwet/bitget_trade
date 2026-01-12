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
)
from utils.instruments import generate_sign
from utils.BitgetSymbolCache import BitgetSymbolCache


class BitgetWS:
    ws: ClientConnection | None = None
    ws_connected: bool = False
    ws_ping_task: asyncio.Task | None = None
    symbol_cache: BitgetSymbolCache | None = None


    def __init__(self) -> None:
        self.symbol_cache = BitgetSymbolCache()


    async def connect(self) -> bool:
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
            return False
        else:
            logger.error(f"[{FUNC_NAME}] Ошибка подключения: {res}")
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
                self.ws_connected = False
                logger.warning(f"[{FUNC_NAME}] Соединение потеряно")

            except Exception as e:
                self.ws_connected = False
                logger.error(f"[{FUNC_NAME}] Ошибка: {e}")


    async def _send_json(self, payload: dict) -> None:
        """ Метод для отправки сообщения на сервер """
        FUNC_NAME = "SEND_JSON"

        if not self.ws or not self.ws_connected:
            logger.warning(f"[{FUNC_NAME}] Соединение потеряно")
            return

        await self.ws.send(dumps(payload))


    async def listen(self) -> None:
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


    async def create_order(
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
                "id": "xxxxx-xxx-xxx-xxxx-xxxxxx",
                "instId": symbol,
                "instType": "USDT-FUTURES",
                "params": {
                    "orderType": "market",
                    "side": side,
                    "size": "2",
                    "marginCoin": "USDT",
                    "force": "gtc",
                    "marginMode": "crossed",
                }
            }],
            "op": "trade"
        }

        await self._send_json(msg)
        logger.info(f"[{FUNC_NAME}] Отправил ордер: {msg}")


    async def start_bitget(self) -> None:
        """ Метод для начала установки соединения с Bitget. Точка входа """
        FUNC_NAME = "START_BITGET"

        while True:
            if not await self.connect():
                logger.warning(f"[{FUNC_NAME}] Соединение разорвано или не было установлено! Повтор через 5 сек...")
                await asyncio.sleep(5)
                continue

            await self.listen()


    def __del__(self) -> None:
        del self.symbol_cache
        logger.debug("[DELETE] Объект торгового bitget-сокета удалён")