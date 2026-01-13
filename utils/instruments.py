from hmac import new
from math import floor
from random import choices
from typing import Literal
from hashlib import sha256
from base64 import b64encode

from config import BITGET_API_SECRET


def generate_sign(
        timestamp: float,
        method: Literal["GET, POST"],
        path: str,
        body: str | None = None
) -> str:
    """
    Функция для создания подписи в теле запроса при его отправке на сервер.

    Аргументы:
        * Timestamp - временная метка
        * Method - строка, описывающая метод для запроса - GET, POST
        * Path - путь до эндпоинта
        * Body - Опционально. Json-дамп тела запроса
    """

    prehash = f"{str(timestamp)}{method}{path}"
    if body:
        prehash += body

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
    """ Функция для генерации уникального идентификатора для отправки ордера """
    allowed_chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_:#+-"
    return ''.join(choices(allowed_chars, k=max_length))