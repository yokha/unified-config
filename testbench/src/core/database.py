import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (AsyncSession, async_sessionmaker,
                                    create_async_engine)
from sqlalchemy.orm import declarative_base

DATABASE_URL = "postgresql+asyncpg://user:password@localhost:5432/testdb"

# SQLAlchemy Async Engine & Session
engine = create_async_engine(DATABASE_URL, echo=True)
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()

# Logger
logger = logging.getLogger(__name__)


async def get_db():
    """Dependency to get async session."""
    async with SessionLocal() as session:
        yield session


async def init_db():
    """Initialize database connection and ensure schemas exist."""
    async with engine.begin() as conn:
        logger.info("📂 Ensuring schemas exist...")
        await conn.run_sync(
            lambda sync_conn: sync_conn.execute(
                text("CREATE SCHEMA IF NOT EXISTS function")
            )
        )
        await conn.run_sync(
            lambda sync_conn: sync_conn.execute(
                text("CREATE SCHEMA IF NOT EXISTS configuration")
            )
        )
        await conn.run_sync(Base.metadata.create_all)

    logger.info("✅ Database initialized successfully!")


async def close_db():
    """Close the database connection."""
    logger.info("🛑 Closing database connection...")
    await engine.dispose()
    logger.info("✅ Database connection closed.")
