from datetime import datetime, timedelta, timezone
import json
import pytest

from unified_config.models.db_model import ConfigHistoryModel
from unified_config.core.db_access import (
    set_config_history,
    fetch_config_history_from_db,
)
from .db_setup import get_session_factory


@pytest.mark.asyncio
async def test_config_history_tracking(config_manager):
    """Ensure history tracking works for config changes."""
    section = "app_settings"
    key = "theme"
    value = "dark"

    await config_manager.set_config(section, key, value)

    # 🔹 Fetch the history response
    history_response = await config_manager.get_config_history(section)

    # 🔹 Extract the "data" list from response
    history_data = history_response.get("data", [])

    assert len(history_data) > 0
    assert history_data[0]["section"] == section
    assert history_data[0]["key"] == key
    assert history_data[0]["new_value"] == value


@pytest.mark.asyncio
async def test_config_history_with_dict(config_manager):
    """Test setting a config with a dictionary and checking history"""
    section, key = "app_settings", "nested_config"
    value = {"theme": "dark", "version": 2}

    # Set config
    await config_manager.set_config(section, key, value)

    # Fetch history
    history = await config_manager.get_config_history(section=section)

    assert history["total_count"] > 0
    assert history["data"][0]["section"] == section
    assert history["data"][0]["key"] == key
    assert history["data"][0]["new_value"] == value  # Ensure dict is stored as JSON


@pytest.mark.parametrize(
    "section, key, value",
    [
        ("general", "float_value", 3.14),
        ("settings", "int_value", 42),
        ("features", "bool_value", True),
        ("preferences", "list_value", [1, 2, 3, "test"]),
        ("advanced", "nested_dict", {"a": 1, "b": [2, 3, {"c": 4}]}),
        ("settings", "empty_string", ""),  # Edge case: Empty string
        (
            "features",
            "deep_nested_dict",
            {"a": {"b": {"c": {"d": [1, 2, {"e": "test"}]}}}},
        ),  # Deeply nested dict
    ],
)
@pytest.mark.asyncio
async def test_config_history_for_different_types(config_manager, section, key, value):
    """Ensure history logging works correctly for different data types."""

    # Step 1: Set initial value with a section
    await config_manager.set_config(section, key, value)

    # Step 2: Retrieve history logs
    history_entries = await config_manager.get_config_history(section, key, limit=100)

    # Assertions
    assert (
        len(history_entries["data"]) == 1
    ), f"Expected 1 history entry for {section}.{key}"

    stored_value = history_entries["data"][0].get("new_value")

    # Handle serialization for lists & dictionaries
    if isinstance(value, (list, dict)):
        stored_value = (
            json.loads(stored_value) if isinstance(stored_value, str) else stored_value
        )
        assert (
            stored_value == value
        ), f"Expected {value}, but got {stored_value} (possible serialization issue)"
    else:
        assert stored_value == value, f"Expected {value}, but got {stored_value}"

    # Fix: Convert the retrieved timestamp to timezone-aware UTC
    stored_timestamp = history_entries["data"][0].get("timestamp")
    if stored_timestamp.tzinfo is None:  # If it's naive, make it UTC-aware
        stored_timestamp = stored_timestamp.replace(tzinfo=timezone.utc)

    # Ensure the timestamp is within an acceptable range (buffer for execution time)
    now = datetime.now(timezone.utc)
    assert (
        now - timedelta(seconds=5) <= stored_timestamp <= now
    ), "Timestamp should be within the last 5 seconds"


@pytest.mark.asyncio
async def test_fetch_config_history_from_db(config_manager):
    """Test fetching configuration history."""
    async for session in get_session_factory():
        try:
            # Insert two history records
            await set_config_history(
                session, "history_section", "key1", "value1", "tester"
            )
            await set_config_history(
                session, "history_section", "key2", "value2", "tester"
            )

            # Fetch full history (should return 2)
            history = await fetch_config_history_from_db(session, ConfigHistoryModel)
            assert history["total_count"] >= 2
            assert len(history["data"]) >= 2

            # Fetch history for a specific section (should return 2)
            section_history = await fetch_config_history_from_db(
                session, ConfigHistoryModel, "history_section"
            )
            assert len(section_history["data"]) >= 2

            # Fetch history for a specific key (should return 1)
            key_history = await fetch_config_history_from_db(
                session, ConfigHistoryModel, "history_section", "key1"
            )
            assert (
                len(key_history["data"]) == 1
            ), f"Expected 1 entry, got {len(key_history['data'])}"
            break
        finally:
            await session.close()
