import os

from redis_manager.redis_manager import RedisManager
from unified_config.core.config_manager import ConfigManager

from database import SessionLocal
from models.config import ConfigHistoryModel, ConfigModel

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
CONFIG_FILE = os.getenv("CONFIG_FILE", "src/config/config.yml")


async def get_config_manager():
    """Dependency that provides a ConfigManager with a fresh DB session per request."""
    redis_client = RedisManager()
    await redis_client.add_node_pool(REDIS_URL)

    async def db_session_factory():
        """Creates a new async session for each request."""
        async with SessionLocal() as session:
            yield session

    config_manager = ConfigManager(
        redis_url=REDIS_URL,
        db_session_factory=db_session_factory,  # Use factory, not a single session
        config_model=ConfigModel,
        config_history_model=ConfigHistoryModel,
        redis_manager=redis_client,
        input_file_path=CONFIG_FILE,
    )
    await config_manager.initialize()
    yield config_manager
    await config_manager.close()
