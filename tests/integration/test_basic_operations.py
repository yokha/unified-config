import json
import asyncio
import pytest
from sqlalchemy import text

from unified_config.models.db_model import ConfigModel
from unified_config.core.db_access import (
    get_config_from_db,
    set_config_in_db,
    delete_config_from_db,
    _upsert_config,
)

from .conftest import REDIS_URL
from .db_setup import get_session_factory
from .helpers import flush_redis_cache


@pytest.mark.asyncio
async def test_set_and_get_config(config_manager):
    """Test setting and retrieving a configuration."""
    section = "app_settings"
    key = "theme"
    value = "dark"

    # Set the config
    await config_manager.set_config(section, key, value, updated_by="test_user")

    # Retrieve from Redis
    async with config_manager.redis_manager.get_client(
        config_manager.redis_url
    ) as client:
        redis_value = await client.get(f"{section}:{key}")
        assert redis_value is not None
        assert json.loads(redis_value) == value  # Value must match

    # Retrieve from DB
    db_value = await config_manager.get_config(section, key)
    assert db_value == value


@pytest.mark.asyncio
async def test_delete_config(config_manager):
    """Test deleting a configuration."""
    section = "app_settings"
    key = "theme"
    value = "dark"

    # Set config first
    await config_manager.set_config(section, key, value, updated_by="test_user")

    # Delete the config
    await config_manager.delete_config(section, key, updated_by="test_user")

    # Ensure it's removed from Redis
    async with config_manager.redis_manager.get_client(
        config_manager.redis_url
    ) as client:
        redis_value = await client.get(f"{section}:{key}")
        assert redis_value is None  # It should be deleted

    # Ensure it's removed from DB
    db_value = await config_manager.get_config(section, key)
    assert db_value is None  # It should be deleted


@pytest.mark.asyncio
async def test_get_entire_section(config_manager):
    """Ensure retrieving an entire section returns all key-value pairs."""

    section = "bulk_fetch"
    test_data = {
        "key1": "value1",
        "key2": 42,
        "key3": {"nested": True},
        "key4": [1, 2, 3],
    }

    # Set multiple values in the same section
    for key, value in test_data.items():
        await config_manager.set_config(section, key, value)

    # Fetch the entire section
    stored_section = await config_manager.get_config(section)

    assert isinstance(stored_section, dict), "Expected dict response for section fetch"
    assert stored_section == test_data, f"Expected {test_data}, got {stored_section}"


@pytest.mark.asyncio
async def test_get_config_from_redis(config_manager, redis_client):
    """Test fetching configuration from Redis cache."""
    section, key, value = "section", "key", "cached_value"
    cache_key = f"{section}:{key}"

    # Step 1: Manually set value in Redis
    async with redis_client.get_client(REDIS_URL) as client:
        await client.set(cache_key, json.dumps(value))

    # Step 2: Fetch from ConfigManager (should read from Redis)
    result = await config_manager.get_config(section, key)

    # Step 3: Verify Redis returned the correct value
    assert result == value, f"Expected '{value}', but got '{result}'"


@pytest.mark.asyncio
async def test_set_config_updates_redis(config_manager, redis_client):
    """Test setting a configuration updates the cache and Redis."""

    section, key, value = "section1", "key1", "value1"
    cache_key = f"{section}:{key}"

    # Step 1: Set config (this should update Redis as well)
    await config_manager.set_config(section, key, value)

    # Step 2: Verify in Redis
    async with redis_client.get_client(REDIS_URL) as client:
        redis_value = await client.get(cache_key)

    assert redis_value is not None, f"Expected {cache_key} to be present in Redis"
    assert (
        json.loads(redis_value) == value
    ), f"Expected '{value}', but got '{json.loads(redis_value)}'"

    # Step 3: Verify in the database to ensure persistence
    async for session in get_session_factory():
        try:
            query = text(
                "SELECT value FROM configuration.configurations WHERE section = :section AND key = :key"
            )
            result = await session.execute(query, {"section": section, "key": key})
            db_value = result.scalar_one_or_none()
            break
        finally:
            await session.close()

    assert db_value is not None, f"Expected {section}:{key} to be in DB"
    assert (
        json.loads(db_value) == value
    ), f"Expected '{value}' in DB, but got '{json.loads(db_value)}'"


@pytest.mark.asyncio
async def test_get_config_not_found(config_manager):
    """Test fetching a non-existent configuration."""
    result = await config_manager.get_config("section", "non_existent_key")
    assert result is None


@pytest.mark.asyncio
async def test_update_config(config_manager, redis_client):
    """Ensure updating a config value works correctly."""

    section = "update_test"
    key = "test_key"

    # Step 1: Set initial value
    await config_manager.set_config(section, key, "initial_value")

    # Step 2: Update value
    await config_manager.set_config(section, key, "updated_value")

    # Step 3: Retrieve and verify update
    final_value = await config_manager.get_config(section, key)

    assert (
        final_value == "updated_value"
    ), f"Expected 'updated_value', got {final_value}"


@pytest.mark.asyncio
async def test_set_config_with_dictionary(config_manager):
    """Test setting an entire section as a dictionary."""
    section_data = {"key1": "value1", "key2": "value2"}

    await config_manager.set_config(section="bulk_section", value=section_data)

    result = await config_manager.get_config("bulk_section")
    assert result == section_data, "Expected full section dictionary"


@pytest.mark.asyncio
async def test_set_config_with_list(config_manager):
    """Test setting an entire section as a list."""
    section_data = ["item1", "item2", "item3"]

    await config_manager.set_config(section="list_section", value=section_data)

    result = await config_manager.get_config("list_section")
    expected_result = section_data

    assert result == expected_result, f"Expected {expected_result}, but got {result}"


@pytest.mark.asyncio
async def test_set_full_section(config_manager):
    """Test setting a full section with multiple key-value pairs using session factory."""

    section, section_data = "test_section_full", {"key1": "value1", "key2": "value2"}

    # Set full section
    await config_manager.set_config(section=section, key=None, value=section_data)

    # Retrieve and validate
    result = await config_manager.get_config(section)
    assert isinstance(
        result, dict
    ), "Expected a dictionary when retrieving a full section"
    assert result == section_data, f"Expected {section_data}, got {result}"


@pytest.mark.asyncio
async def test_listen_to_config_changes(config_manager, redis_client):
    """Ensure listen_to_config_changes correctly processes Redis Pub/Sub events."""

    received_events = asyncio.Queue()  # Store received events

    async def mock_callback(change_data):
        await received_events.put(change_data)  # Store received events

    # Step 1: Start listener in background
    listener_task = asyncio.create_task(
        config_manager.listen_to_config_changes(mock_callback)
    )

    # Step 2: Allow some time for listener to initialize
    await asyncio.sleep(1.0)  # Ensure Redis connection is established

    # Step 3: Send a test event via Redis
    test_event = {
        "action": "set",
        "section": "test_section",
        "key": "test_key",
        "timestamp": "2025-02-16T18:44:44Z",
        "updated_by": "test_user",
    }

    async with redis_client.get_client(config_manager.redis_url) as client:
        await client.publish("config_changes", json.dumps(test_event))

    # Step 4: Wait and retry if event is not received immediately
    retries = 3
    event = None

    for attempt in range(retries):
        try:
            event = await asyncio.wait_for(received_events.get(), timeout=2.0)
            break  # Exit loop once an event is received
        except asyncio.TimeoutError:
            print(f"⚠️ Retry {attempt+1}/{retries}: No event received, retrying...")
            await asyncio.sleep(1.0)  # Wait before retrying

    # Step 5: Verify the event was received
    assert (
        event is not None
    ), "❌ Expected at least one event to be received from Redis Pub/Sub."
    assert event["section"] == "test_section"
    assert event["key"] == "test_key"
    assert event["action"] == "set"
    assert event["updated_by"] == "test_user"

    # Step 6: Cleanup listener task
    listener_task.cancel()
    try:
        await listener_task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_get_config_from_db(config_manager):
    """Test fetching configuration from the database."""
    async for session in get_session_factory():
        try:
            await config_manager.set_config("test_section", "key1", "value1")
            await config_manager.set_config("test_section", "key2", "value2")

            # Fetch a specific key
            value = await get_config_from_db(
                session, ConfigModel, "test_section", "key1"
            )
            assert value == "value1"

            # Fetch entire section
            section_data = await get_config_from_db(
                session, ConfigModel, "test_section"
            )
            assert section_data == {"key1": "value1", "key2": "value2"}

            # Fetch all configs
            all_configs = await get_config_from_db(session, ConfigModel)
            assert isinstance(all_configs, list)
            assert len(all_configs) > 0
            break
        finally:
            await session.close()


@pytest.mark.asyncio
async def test_set_config_in_db(config_manager):
    """Test inserting/updating configurations in the database."""
    async for session in get_session_factory():
        try:
            # Set single key-value pair
            await set_config_in_db(
                session, ConfigModel, "set_test_section", "key1", "value1"
            )
            stored_value = await get_config_from_db(
                session, ConfigModel, "set_test_section", "key1"
            )
            assert stored_value == "value1"

            # Set entire section
            section_data = {"key2": "value2", "key3": "value3"}
            await set_config_in_db(
                session, ConfigModel, "set_test_section", value=section_data
            )
            stored_section = await get_config_from_db(
                session, ConfigModel, "set_test_section"
            )
            assert stored_section == {"key2": "value2", "key3": "value3"}

            # Test invalid type
            with pytest.raises(ValueError):
                await set_config_in_db(
                    session,
                    ConfigModel,
                    "set_test_section",
                    key="invalid",
                    value=object(),
                )
            break
        finally:
            await session.close()


@pytest.mark.asyncio
async def test_upsert_config(config_manager):
    """Test inserting/updating configuration using _upsert_config."""
    async for session in get_session_factory():
        try:
            # Insert a new config
            await _upsert_config(
                session, ConfigModel, "upsert_section", "key1", "value1"
            )
            result = await get_config_from_db(
                session, ConfigModel, "upsert_section", "key1"
            )
            assert result == "value1"

            # Update existing config
            await _upsert_config(
                session, ConfigModel, "upsert_section", "key1", "new_value"
            )
            updated_result = await get_config_from_db(
                session, ConfigModel, "upsert_section", "key1"
            )
            assert updated_result == "new_value"
            break
        finally:
            await session.close()


@pytest.mark.asyncio
async def test_delete_config_from_db(config_manager):
    """Test deleting configurations from the database."""
    async for session in get_session_factory():
        try:
            await set_config_in_db(
                session, ConfigModel, "delete_test_section", "key1", "value1"
            )
            await set_config_in_db(
                session, ConfigModel, "delete_test_section", "key2", "value2"
            )

            # Delete specific key
            deleted = await delete_config_from_db(
                session, ConfigModel, "delete_test_section", "key1"
            )
            assert deleted is True

            # Verify key is removed
            value = await get_config_from_db(
                session, ConfigModel, "delete_test_section", "key1"
            )
            assert value is None

            # Delete entire section
            deleted_section = await delete_config_from_db(
                session, ConfigModel, "delete_test_section"
            )
            assert deleted_section is True

            # Verify section is removed
            value = await get_config_from_db(
                session, ConfigModel, "delete_test_section"
            )
            assert value is None

            # Try deleting non-existent key
            deleted_non_existent = await delete_config_from_db(
                session, ConfigModel, "fake_section", "fake_key"
            )
            assert deleted_non_existent is False
        finally:
            await session.close()


@pytest.mark.asyncio
async def test_close(config_manager):
    """Ensure config manager closes Redis and DB sessions properly."""

    # Step 1: Close the manager
    await config_manager.close()

    # Step 2: Ensure DB session is closed
    with pytest.raises(Exception):
        await config_manager.db_session.execute(
            text("SELECT 1")
        )  # Should fail if session is closed

    # Step 3: Ensure Redis is closed
    with pytest.raises(Exception):
        async with config_manager.redis_manager.get_client(REDIS_URL) as client:
            await client.ping()  # Should fail if Redis is closed


@pytest.mark.asyncio
async def test_config_persistence_across_redis_and_db(config_manager):
    """Ensure configs persist across Redis and DB."""
    section = "app_settings"
    key = "font_size"
    value = 14

    await config_manager.set_config(section, key, value)

    async with config_manager.redis_manager.get_client(
        config_manager.redis_url
    ) as redis_client:
        cached_value = await redis_client.get(f"{section}:{key}")

    assert cached_value is not None
    assert json.loads(cached_value) == value
    await flush_redis_cache(config_manager)
