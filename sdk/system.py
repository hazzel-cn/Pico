import aiofiles
from loguru import logger

async def get_cpu_temperature() -> float:
    """
    Get the current CPU temperature from the thermal zone file.
    Returns 0.0 if reading fails.
    """
    try:
        # logger.info("Reading CPU Temperature from kernel...") 
        # Commented out verbose log to reduce noise if queried frequently, 
        # or keep it debug level if logic allows. 
        # Keeping it info for now as per previous behavior, or maybe reduce noise? 
        # User wants "Hacker Mode", maybe less noise? 
        # But previous code had it. I'll keep it simple.
        async with aiofiles.open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            content = await f.read()
            temp = float(content) / 1000.0
            return temp
    except Exception as e:
        logger.error(f"Failed to read CPU temperature: {e}")
        return 0.0
