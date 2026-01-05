from aiogram import Bot, Dispatcher
from loguru import logger
import sdk.config as config

# Initialize Bot and Dispatcher here (Infrastructure)
# Service will import these to register handlers and start polling.

if not config.TELEGRAM_BOT_TOKEN:
    logger.warning("TELEGRAM_BOT_TOKEN not set in config. Bot may fail to start.")
    bot = None
else:
    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)


dp = Dispatcher()

def is_user_allowed(user_id: int) -> bool:
    """Check if the user is authorized based on config."""
    if not config.TELEGRAM_ALLOWED_USERS:
        return True # Open if no whitelist defined (or handle differently)
    return user_id in config.TELEGRAM_ALLOWED_USERS
