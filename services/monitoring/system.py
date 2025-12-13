import aiofiles
from core.config import settings
from core.logger import logger
from core.bark import bark

async def get_cpu_temperature() -> float:
    try:
        logger.info("Reading CPU Temperature from kernel...")
        async with aiofiles.open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            content = await f.read()
            temp = float(content) / 1000.0
            logger.info(f"CPU Temperature Read: {temp}")
            return temp
    except Exception as e:
        logger.error(f"Failed to read CPU temperature: {e}")
        return 0.0

async def check_system_temp():
    temp = await get_cpu_temperature()
    logger.info(f"System Temperature: {temp:.1f}°C")
    
    if temp > settings.TEMP_THRESHOLD:
        logger.warning(f"High Temperature Detected: {temp:.1f}°C")
        await bark.send(
            title="High CPU Temp",
            body=f"Raspberry Pi is running hot: {temp:.1f}°C",
            level="critical",
            group="pico_system_monitor"
        )
