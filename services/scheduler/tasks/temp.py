from loguru import logger
from sdk.system import get_cpu_temperature
from sdk.bark import bark

TEMP_THRESHOLD = 75.0

async def monitor_system_temp():
    """Check system temperature and alert if high."""
    temp = await get_cpu_temperature()
    logger.info(f"System Temperature: {temp:.1f}°C")
    
    if temp > TEMP_THRESHOLD:
        logger.warning(f"High Temperature Detected: {temp:.1f}°C")
        await bark.send(
            title="High CPU Temp",
            body=f"Raspberry Pi is running hot: {temp:.1f}°C",
            level="critical",
            group="pico_system_monitor"
        )
