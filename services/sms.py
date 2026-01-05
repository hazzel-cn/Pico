import asyncio
from loguru import logger
import sdk.sms
from sdk.bark import bark

async def main():
    logger.add("logs/pico.log", rotation="5 MB", level="INFO")
    logger.info("Initializing SMS Service...")
    
    try:
        # The Service Polices: "When I get an SMS, I send a Bark notification."
        # The SDK provides the Stream.
        async for phone, text in sdk.sms.monitor_inbox():
            logger.info(f"Received SMS from {phone}")
            await bark.send(
                title=f"SMS: {phone}",
                body=text,
                group="sms",
                level="timeSensitive"
            )
            
    except asyncio.CancelledError:
        logger.info("SMS Service stopping...")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
