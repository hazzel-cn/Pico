from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from core.logger import logger
from services.monitoring.system import check_system_temp


scheduler = AsyncIOScheduler()

def start_scheduler():
    from core.config import settings
    
    logger.info("Starting Scheduler...")
    
    if settings.ENABLE_SYSTEM_TEMP:
        scheduler.add_job(check_system_temp, "interval", minutes=5)
    else:
        logger.info("System Temp Monitor Disabled via Config.")
    

    scheduler.start()
    
    jobs = [job.name for job in scheduler.get_jobs()]
    logger.info(f"Scheduler active with jobs: {jobs}")

def stop_scheduler():
    logger.info("Stopping Scheduler...")
    scheduler.shutdown()
