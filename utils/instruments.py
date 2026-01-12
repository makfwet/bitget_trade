from hmac import new
from hashlib import sha256
from typing import Literal
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