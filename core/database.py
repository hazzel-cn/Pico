from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite+aiosqlite:///pico.db"

# Models are defined in services/monitoring/models.py (REMOVED)
# We import them inside init_db or ensure they are imported before SQLModel.metadata.create_all is called.


from core.logger import logger

engine = create_async_engine(DATABASE_URL, echo=False, future=True)

async def init_db():
    logger.info("Initializing Database...")
    async with engine.begin() as conn:
        # await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)

async def get_session() -> AsyncSession:
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
