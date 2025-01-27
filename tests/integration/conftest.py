import asyncio
import pytest_asyncio
from sqlalchemy.sql import text
from redis_manager.redis_manager import RedisManager
from unified_config.core.config_manager import ConfigManager
from unified_config.models.db_model import ConfigModel, ConfigHistoryModel
from .db_setup import setup_database, get_session_factory

REDIS_URL = "redis://localhost:6380"


@pytest_asyncio.fixture(scope="session", autouse=True)
def event_loop():
    """Create a session-wide event loop."""
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_db(request):
    """Ensure the test database is initialized before running tests."""
    print(
        "🔄 Running setup_db() → Ensuring clean database before test..."
    )  # Debugging print
    await setup_database()  # Ensure tables exist

    # session_factory = get_session_factory()
    async for session in get_session_factory():
        try:
            print("🧹 Cleaning up database before test execution...")  # Debugging print
            await session.execute(text("DELETE FROM configuration.configurations;"))
            await session.execute(text("DELETE FROM configuration.config_history;"))
            await session.commit()
            break
        finally:
            await session.close()

    # Finalizer to clean up **after** the test finishes
    async def teardown():
        print("🗑️ Running teardown() → Cleaning up database after test...")
        async for session in get_session_factory():
            try:
                await session.execute(text("DELETE FROM configuration.configurations;"))
                await session.execute(text("DELETE FROM configuration.config_history;"))
                await session.commit()
                break
            finally:
                await session.close()

    # Run `teardown()` in the existing event loop
    event_loop = request.getfixturevalue("event_loop")
    request.addfinalizer(lambda: event_loop.run_until_complete(teardown()))


# @pytest_asyncio.fixture
# async def db_session_factory():
#     """Fixture to provide a session factory for ConfigManager."""
#     return get_session_factory  # Use the same session factory for all tests


@pytest_asyncio.fixture
async def redis_client():
    """Fixture to initialize and return a RedisManager instance."""
    redis_manager = RedisManager()
    await redis_manager.add_node_pool(REDIS_URL)
    redis_manager.start_cleanup()

    async with redis_manager.get_client(REDIS_URL) as client:
        await client.flushdb()  # Ensure Redis is clean before each test

    yield redis_manager

    # Cleanup Redis after tests
    redis_manager.stop_cleanup()
    redis_manager.stop_health_checks()
    await redis_manager.close_all_pools()


@pytest_asyncio.fixture
async def config_manager(redis_client):
    """Fixture to initialize and return a ConfigManager instance with session factory."""
    manager = ConfigManager(
        redis_url=REDIS_URL,  # Use the correct test Redis URL
        db_session_factory=get_session_factory,  # Pass session factory instead of a single session
        config_model=ConfigModel,
        config_history_model=ConfigHistoryModel,
        redis_manager=redis_client,
    )
    await manager.initialize()  # Ensure it's fully initialized before testing
    yield manager
    await manager.close()  # Proper cleanup
