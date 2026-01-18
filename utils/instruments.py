from hmac import new
from math import floor
from random import choices
from typing import Literal
from hashlib import sha256
from base64 import b64encode

from config import BITGET_API_SECRET, BITGET_API_KEY, BITGET_API_PASSPHRASE


def generate_sign(
    timestamp: int,
    method: Literal["GET, POST"],
    path: str,
    body: str = ""
) -> str:
    """
    Функция для создания подписи в теле запроса при его отправке на сервер.

    Аргументы:
        * Timestamp - временная метка
        * Method - строка, описывающая метод для запроса - GET, POST
        * Path - путь до эндпоинта
        * Body - Опционально. Json-дамп тела запроса
    """

    prehash = str(timestamp) + method + path + body

    return b64encode(
        new(
            BITGET_API_SECRET.encode(),
            prehash.encode(),
            sha256,
        ).digest()
    ).decode()


def calc_qty(usdt: float, price: float, qty_step: float) -> float | int:
    """ Функция для расчета qty """
    raw_qty = usdt / price
    precision = abs(str(qty_step)[::-1].find("."))
    return round(floor(raw_qty / qty_step) * qty_step, 1) if precision > 0 else int(raw_qty)


def generate_order_id(max_length: int = 40) -> str:
    """ Функция для генерации уникального идентификатора для отправки ордера по вебсокету """
    allowed_chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_:#+-"
    return ''.join(choices(allowed_chars, k=max_length))


def generate_headers(
    endpoint: str,
    timestamp: int,
    method: Literal["GET, POST"],
    body: str = ""
) -> dict:
    """ Функция-генератор заголовков для http-запросов """
    return {
        "ACCESS-KEY": BITGET_API_KEY,
        "ACCESS-SIGN": generate_sign(timestamp, method, endpoint, body),
        "ACCESS-TIMESTAMP": str(timestamp),
        "ACCESS-PASSPHRASE": BITGET_API_PASSPHRASE,
        "Content-Type": "application/json",
    }


def response_prettifier(
    timestamp: int,
    response_dict: dict,
) -> int | tuple[int, str] | None:
    """
    Функция для обработки полученных ответов от Bitget.

    Возвращает:
        * задержку (при успешном статус коде)
        * кортеж с задержкой и сообщением (при неуспешном статус коде)
        * None при ошибке валидации данных
    """
    if not isinstance(response_dict, dict) or not isinstance(timestamp, int):
        return

    msg = response_dict.get('msg')
    status_code = response_dict.get("code")
    latency = response_dict.get("requestTime") - timestamp

    if not all((msg, status_code, latency)):
        return

    if status_code == "00000":
        return True, latency, msg
    else:
        return False, latency, msg
