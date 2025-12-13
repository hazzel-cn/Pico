import sys
import os
from loguru import logger
from core.bark import bark

# Calculate project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(BASE_DIR, "logs", "pico.log")

# Configure logger
logger.remove()  # Remove default handler
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
)
# File logging with rotation and retention to save space (SD Card friendly)
logger.add(
    LOG_FILE, 
    rotation="5 MB", 
    retention="7 days", 
    level="INFO",
    compression="zip" # Compress old logs to save even more space
)

async def bark_sink(message):
    """
    Loguru sink that sends critical/error logs to Bark.
    """
    try:
        record = message.record
        # Avoid recursive loops if bark itself logs an error
        if "bark" in record["name"]:
            return

        level_name = record["level"].name
        if level_name in ["ERROR", "CRITICAL"]:
            log_msg = record["message"]
            alert_title = f"Pico Error: {record['name']}"
            await bark.send(
                body=f"{level_name}: {log_msg}\nFile: {record['file'].name}:{record['line']}",
                title=alert_title,
                group="pico_errors",
                level="critical" if level_name == "CRITICAL" else "timeSensitive"
            )
    except Exception:
        # If bark sink fails, just print to stderr to avoid crash loop
        pass

# Add the async sink
logger.add(bark_sink, level="ERROR")
