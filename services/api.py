from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_session

from services.monitoring.system import get_cpu_temperature
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1")

# --- Schemas ---


# --- System API ---
@router.get("/system/temperature")
async def get_temperature():
    temp = await get_cpu_temperature()
    return {"temperature": temp}



@router.get("/system/logs")
async def get_logs(lines: int = 50):
    from core.logger import LOG_FILE
    import aiofiles
    
    if lines > 200:
        lines = 200 # Cap it
        
    try:
        async with aiofiles.open(LOG_FILE, "r") as f:
            content = await f.readlines()
            return {"logs": content[-lines:]}
    except Exception as e:
        return {"error": str(e)}
