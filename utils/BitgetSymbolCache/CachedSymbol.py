class CachedSymbol:
    """ Простой датакласс для хранения кэшированного символа """
    price: float
    min_qty: float
    qty_step: float

    def __init__(self, price: float, min_qty: float, qty_step: float) -> None:
        self.price = price
        self.min_qty = min_qty
        self.qty_step = qty_step