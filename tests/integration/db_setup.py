from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.sql import text
from unified_config.models.db_model import Base

# Database connection URL for testing
DATABASE_URL = "postgresql+asyncpg://postgres:password@localhost:5433/integration_db"

# Define the engine and session factory
engine = create_async_engine(DATABASE_URL, echo=True)
async_session_factory = async_sessionmaker(
    bind=engine, expire_on_commit=False, class_=AsyncSession
)  # Session factory


async def setup_database():
    """Initialize the test database."""
    async with engine.begin() as conn:
        # Explicitly create schemas before creating tables
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS configuration"))
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS function"))
        # Now create tables in the correct schema
        await conn.run_sync(Base.metadata.create_all)


async def get_session_factory():
    """Returns a new session factory for ConfigManager."""
    async with async_session_factory() as session:
        yield session
