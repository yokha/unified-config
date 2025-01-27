import asyncio
import pytest
from fastapi import HTTPException

from unified_config.core.config_manager import ConfigManager
from unified_config.models.db_model import ConfigModel, ConfigHistoryModel
from .db_setup import get_session_factory


@pytest.mark.asyncio
async def test_concurrent_delete_config(config_manager):
    """Ensure concurrent deletions do not cause race conditions."""

    section, key = "concurrent_test", "shared_key"

    # Step 1: Set the config before attempting deletion
    await config_manager.set_config(section, key, "to_be_deleted")

    # Step 2: Run two concurrent delete attempts
    async def safe_delete():
        try:
            await config_manager.delete_config(section, key)
        except HTTPException as e:
            assert e.status_code == 404, f"Unexpected error: {e}"  # Allow 404

    await asyncio.gather(safe_delete(), safe_delete())

    # Step 3: Ensure the key is deleted
    deleted_value = await config_manager.get_config(section, key)
    assert (
        deleted_value is None
    ), f"Expected config {section}.{key} to be deleted, but got {deleted_value}"

    # Step 4: Ensure history logs the deletion
    history_entries = await config_manager.get_config_history(section, key, limit=100)
    assert (
        len(history_entries["data"]) >= 2
    ), "Expected at least 2 history entries (set + delete)"
    assert (
        history_entries["data"][0].get("new_value") is None
    ), "Expected last history entry to indicate deletion"


@pytest.mark.asyncio
async def test_concurrent_set_config(config_manager):
    """Ensure concurrent set_config calls do not cause race conditions."""

    section, key = "concurrent_test", "shared_key"

    async def set_value(value):
        await config_manager.set_config(section, key, value)

    # Step 1: Run two concurrent set operations with different values
    await asyncio.gather(
        set_value("value_1"),
        set_value("value_2"),
    )

    # Step 2: Retrieve the value (should match the last write)
    final_value = await config_manager.get_config(section, key)

    assert final_value in [
        "value_1",
        "value_2",
    ], f"Unexpected final value: {final_value}"

    # Step 3: Ensure history logs both updates
    history_entries = await config_manager.get_config_history(section, key, limit=10)
    assert (
        len(history_entries["data"]) >= 2
    ), "Expected at least 2 history entries (2 updates)"


@pytest.mark.asyncio
async def test_concurrent_get_config(config_manager):
    """Ensure multiple concurrent get_config calls return consistent values."""

    section, key = "concurrent_test", "shared_key"
    expected_value = "stable_value"

    # Step 1: Set a known value before reading it concurrently
    await config_manager.set_config(section, key, expected_value)

    async def get_value():
        return await config_manager.get_config(section, key)

    # Step 2: Run multiple concurrent reads
    results = await asyncio.gather(
        get_value(),
        get_value(),
        get_value(),
    )

    # Step 3: Ensure all reads returned the same value
    assert all(
        result == expected_value for result in results
    ), f"Inconsistent results: {results}"


@pytest.mark.asyncio
async def test_concurrent_update_config(config_manager, redis_client):
    """Ensure concurrent updates to a config entry do not corrupt data."""

    section, key = "concurrent_test", "nested_dict"

    # Step 1: Set an initial dictionary
    await config_manager.set_config(section, key, {"a": 1, "b": 2})

    async def update_a():
        await config_manager.set_config(section, key, {"a": 42, "b": 2})

    async def update_b():
        await config_manager.set_config(section, key, {"a": 1, "b": 99})

    # Step 2: Perform two concurrent updates
    await asyncio.gather(update_a(), update_b())

    # Step 3: Retrieve the final value
    final_value = await config_manager.get_config(section, key)

    # Step 4: Ensure at least one update is reflected
    assert final_value in [
        {"a": 42, "b": 2},
        {"a": 1, "b": 99},
    ], f"Unexpected final value: {final_value}"

    # Step 5: Ensure history logs both updates
    history_entries = await config_manager.get_config_history(section, key, limit=10)
    assert (
        len(history_entries["data"]) >= 2
    ), "Expected at least 2 history entries (2 updates)"


@pytest.mark.asyncio
async def test_concurrent_bulk_update_config(config_manager, redis_client):
    """Ensure concurrent bulk updates work correctly."""

    section1 = "update_test_section1"
    section2 = "update_test_section2"

    # Step 1: Set initial values using bulk set
    initial_configs = {
        section1: {"key1": "value1", "key2": "value2"},
        section2: {"key_a": "valueA", "key_b": "valueB"},
    }
    await config_manager.set_bulk_config(initial_configs)

    # Step 2: Define two different bulk updates
    bulk_update_1 = {
        section1: {"key1": "new_value1"},
        section2: {"key_a": "new_valueA"},
    }
    bulk_update_2 = {
        section1: {"key2": "new_value2"},
        section2: {"key_b": "new_valueB"},
    }

    # Step 3: Run concurrent bulk updates
    await asyncio.gather(
        config_manager.set_bulk_config(bulk_update_1),
        config_manager.set_bulk_config(bulk_update_2),
    )

    # Step 4: Verify all updates were applied correctly
    for section, keys in {**bulk_update_1, **bulk_update_2}.items():
        retrieved_configs = await config_manager.get_config(section)
        for key, expected_value in keys.items():
            assert (
                retrieved_configs[key] == expected_value
            ), f"❌ Mismatch: {section}.{key} = {retrieved_configs[key]}, expected {expected_value}"


@pytest.mark.asyncio
async def test_multiple_clients_syncing_configs(config_manager):
    """Ensure multiple config manager instances stay in sync via DB and Redis."""

    section = "sync_test"
    key = "refresh_rate"
    value = 60

    # Create another independent instance using a fresh session
    config_manager_2 = ConfigManager(
        redis_url=config_manager.redis_url,
        db_session_factory=get_session_factory,  # Use factory instead of shared session
        config_model=ConfigModel,
        config_history_model=ConfigHistoryModel,
        redis_manager=config_manager.redis_manager,  # Redis stays shared
    )

    await config_manager_2.initialize()
    await config_manager_2.set_config(section, key, value)

    # Check from the first instance (ensure it reflects the change)
    retrieved_value = await config_manager.get_config(section, key)
    assert retrieved_value == value, f"Expected {value}, got {retrieved_value}"

    await config_manager_2.close()
