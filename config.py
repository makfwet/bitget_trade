from loguru import logger


logger.add(
    "logs/parsing_logs.log",
    level="INFO",
    rotation="10 MB",
    retention="10 days",
    enqueue=True,
)

WS_BASE_URL = "wss://ws.bitget.com/v2/ws/private"
API_BASE_URL = "https://api.bitget.com"

PING_INTERVAL = 30
CACHE_UPDATE_INTERVAL = 5

BITGET_API_KEY = ""
BITGET_API_SECRET = ""
BITGET_API_PASSPHRASE = ""
