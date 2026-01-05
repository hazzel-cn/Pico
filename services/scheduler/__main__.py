import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from services.scheduler.tasks.temp import monitor_system_temp
from services.scheduler.tasks.uscis import monitor_uscis

scheduler = AsyncIOScheduler()

def start_scheduler():
    logger.info("Starting Refactored Scheduler...")
    
    # 5 min temp check
    scheduler.add_job(monitor_system_temp, "interval", minutes=5)
    
    # 1 hour USCIS check, run immediately on start
    from datetime import datetime
    scheduler.add_job(monitor_uscis, "interval", hours=1, next_run_time=datetime.now())
    
    scheduler.start()
    
    jobs = [job.name for job in scheduler.get_jobs()]
    logger.info(f"Scheduler active with jobs: {jobs}")

def stop_scheduler():
    logger.info("Stopping Scheduler...")
    scheduler.shutdown()

async def main():
    logger.add("logs/pico.log", rotation="5 MB", level="INFO")
    logger.info("Initializing Pico Scheduler Service (Integrated)...")
    start_scheduler()
    
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        stop_scheduler()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        stop_scheduler()
        logger.info("Scheduler stopped.")
