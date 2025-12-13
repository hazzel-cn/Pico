import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from core.logger import logger
from core.database import init_db
from services.scheduler import start_scheduler, stop_scheduler
from services.sms import sms_service
from services.api import router as api_router
from services.telegram_bot import start_telegram_bot

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Pico service starting up...")
    await init_db()
    
    from core.config import settings
    
    # Start Services
    start_scheduler()
    if settings.ENABLE_SMS_FORWARDER:
        sms_service.start()
    else:
        logger.info("SMS Forwarder Disabled via Config.")
    
    # Start Telegram Bot in Background
    telegram_task = asyncio.create_task(start_telegram_bot())
    
    yield
    # Shutdown
    logger.info("Pico service shutting down...")
    
    # Cancel Telegram Bot (stops infinite polling loop)
    telegram_task.cancel()
    try:
        await telegram_task
    except asyncio.CancelledError:
        logger.info("Telegram Bot stopped.")
        
    if settings.ENABLE_SMS_FORWARDER:
        sms_service.stop()
    stop_scheduler()

app = FastAPI(title="Pico", lifespan=lifespan)

# Mount API Router
app.include_router(api_router)

@app.get("/")
async def root():
    return {"message": "Pico Framework is running"}

@app.get("/health")
async def health():
    return {"status": "ok"}
