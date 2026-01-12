from loguru import logger

from bitget_rest import place_market_order


def normalize_qty(qty: float, min_qty: float, step: float) -> float:
    if qty < min_qty:
        raise ValueError(f"qty {qty} < min_qty {min_qty}")

    steps = int(qty / step)
    normalized = steps * step

    if normalized < min_qty:
        raise ValueError("normalized qty < min_qty")

    return round(normalized, 8)


class BitgetTrader:
    """
    Единственный интерфейс для парсеров
    """

    def __init__(self, cache):
        self.cache = cache

    async def open_position(self, symbol: str, side: str, qty: float):
        symbol = symbol.upper()
        side = side.lower()  # buy / sell

        data = self.cache.get(symbol)
        if not data:
            raise ValueError(f"Symbol {symbol} not found in cache")

        qty_norm = normalize_qty(qty, data["min_qty"], data["qty_step"])

        logger.info(
            f"[TRADE] {symbol} {side} qty={qty} -> normalized={qty_norm}"
        )

        res = await place_market_order(
            symbol=symbol,
            side=side,
            size=qty_norm,
        )

        logger.info(f"[REST ORDER RESULT] {res}")
        return res
