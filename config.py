from os import getenv
from pathlib import Path

from loguru import logger
from dotenv import load_dotenv


load_dotenv(Path(__file__).parent / '.env')

logger.add(
    "logs/parsing_logs.log",
    level="INFO",
    rotation="10 MB",
    retention="10 days",
    enqueue=True,
)

TRADE_USDT = 10

RECONNECT_INTERVAL = 5
PING_INTERVAL = 30
CACHE_UPDATE_INTERVAL = 86400

WS_BASE_URL = "wss://ws.bitget.com/v2/ws/private"
API_BASE_URL = "https://api.bitget.com"
BITGET_API_KEY = getenv("BITGET_API_KEY")
BITGET_API_SECRET = getenv("BITGET_API_SECRET")
BITGET_API_PASSPHRASE = getenv("BITGET_API_PASSPHRASE")
