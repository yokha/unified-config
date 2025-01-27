import json
import pytest
from fastapi import HTTPException


@pytest.mark.parametrize(
    "section, key, value, should_exist",
    [
        ("general", "non_existent_key", None, False),  # ❌ Key does not exist
        ("typed", "string_value", "test_string", True),  # String
        ("typed", "int_value", 42, True),  # Integer
        ("typed", "float_value", 3.14, True),  # Float
        ("typed", "bool_value", True, True),  # Boolean
        ("typed", "list_value", [1, 2, 3], True),  # List
        ("typed", "dict_value", {"key1": "value1", "key2": 2}, True),  # Dictionary
        (
            "deep",
            "nested_dict",
            {"a": {"b": {"c": {"d": "nested"}}}},
            True,
        ),  # Deep dictionary
    ],
)
@pytest.mark.asyncio
async def test_get_config_edge_cases(config_manager, section, key, value, should_exist):
    """Test edge cases for get_config."""

    # Set the value first (if expected to exist)
    if should_exist:
        await config_manager.set_config(section, key, value)

    # Retrieve the config
    stored_value = await config_manager.get_config(section, key)

    if not should_exist:
        assert (
            stored_value is None
        ), f"Expected None for missing key {key}, but got {stored_value}"
    else:
        if isinstance(value, (list, dict)):
            stored_value = (
                json.loads(stored_value)
                if isinstance(stored_value, str)
                else stored_value
            )

        assert stored_value == value, f"Expected {value}, but got {stored_value}"


@pytest.mark.asyncio
async def test_delete_config_edge_cases(config_manager):
    """Ensure delete_config works as expected with different scenarios."""

    section, key = "test_section", "test_key"

    # Step 1: Set a config before deleting
    await config_manager.set_config(section, key, "test_value")

    # Step 2: Delete the config
    await config_manager.delete_config(section, key)

    # Step 3: Ensure Redis cache is cleared
    async with config_manager.redis_manager.get_client(
        config_manager.redis_url
    ) as redis_client:
        exists = await redis_client.exists(f"{section}:{key}")
        assert (
            exists == 0
        ), f"Expected Redis key {section}:{key} to be deleted, but it still exists!"

    # Step 4: Try to fetch the deleted key
    deleted_value = await config_manager.get_config(section, key)
    assert (
        deleted_value is None
    ), f"Expected None for deleted config {section}.{key}, but got {deleted_value}"

    # Step 5: Ensure history still contains the deleted entry
    history_entries = await config_manager.get_config_history(section, key, limit=100)
    assert (
        len(history_entries["data"]) >= 2
    ), f"Expected at least 2 history entries (set + delete) for {section}.{key}"

    # Ensure last history entry reflects deletion
    last_entry = history_entries["data"][0]
    assert (
        last_entry.get("new_value") is None
    ), "Expected last history entry to indicate deletion"

    # Step6: Try deleting a non-existent key (should raise 404 HTTPException)
    with pytest.raises(HTTPException) as exc_info:
        await config_manager.delete_config(section, "non_existent_key")

    assert (
        exc_info.value.status_code == 404
    ), "Expected 404 error for non-existent config deletion."
    assert (
        exc_info.value.detail == "Config not found."
    ), "Expected 'Config not found.' message."

    # Step 7: Set multiple keys in a section and delete the entire section
    await config_manager.set_config(section, "key1", "value1")
    await config_manager.set_config(section, "key2", "value2")

    # Delete the section
    await config_manager.delete_config(section)

    # Ensure all keys in the section are deleted
    section_data = await config_manager.get_config(section)
    assert (
        section_data is None or section_data == {}
    ), f"Expected empty section after deletion, but got {section_data}"

    # Step 8: Ensure Redis cache is cleared
    async with config_manager.redis_manager.get_client(
        config_manager.redis_url
    ) as redis_client:
        exists = await redis_client.exists(f"{section}:__full_section__")
        assert (
            exists == 0
        ), f"Expected Redis key {section}:__full_section__ to be deleted, but it still exists!"


@pytest.mark.asyncio
async def test_set_config_invalid_type(config_manager):
    """Test handling of invalid types while setting a config."""
    with pytest.raises(
        ValueError, match="Configuration value must be JSON serializable"
    ):
        await config_manager.set_config(
            section="invalid_section", key="invalid_key", value=object()
        )


@pytest.mark.asyncio
async def test_get_non_existent_config(config_manager):
    """Ensure retrieving a non-existent config returns None."""

    section = "non_existent_section"
    key = "non_existent_key"

    value = await config_manager.get_config(section, key)

    assert value is None, f"Expected None for non-existent config, got {value}"


@pytest.mark.asyncio
async def test_config_rejects_none(config_manager):
    """Ensure that None is not allowed as a top-level config value."""

    section, key, value = "invalid", "none_value", None

    with pytest.raises(ValueError, match="Configuration value cannot be None"):
        await config_manager.set_config(section, key, value)


@pytest.mark.asyncio
async def test_set_invalid_config_value(config_manager):
    """Ensure invalid config values (e.g., sets) are rejected."""

    section = "invalid_test"
    key = "invalid_key"

    with pytest.raises(
        ValueError, match="Configuration value must be JSON serializable"
    ):
        await config_manager.set_config(
            section, key, {"valid": "dict", "invalid": {1, 2, 3}}
        )  # ❌ Contains a `set`


@pytest.mark.parametrize(
    "section, key, value, should_fail",
    [
        ("general", "overwrite_key", "initial_value", False),  # Overwriting test
        ("invalid", "", "some_value", True),  # ❌ Empty key should fail
        ("config", "empty_dict", {}, False),  # Empty dictionary allowed
        ("config", "empty_list", [], False),  # Empty list allowed
        ("stress", "large_list", list(range(10000)), False),  # Large list
        (
            "stress",
            "large_dict",
            {f"key_{i}": i for i in range(5000)},
            False,
        ),  # Large dictionary
        (
            "deep",
            "nested_dict",
            {"a": {"b": {"c": {"d": [1, 2, {"e": "test"}]}}}},
            False,
        ),  # Deeply nested dictionary
        (
            "invalid",
            "set_value",
            {1, 2, 3},
            True,
        ),  # ❌ Set should fail (not JSON serializable)
        ("boolean", "false_value", False, False),  # Boolean value should work
    ],
)
@pytest.mark.asyncio
async def test_set_config_edge_cases(config_manager, section, key, value, should_fail):
    """Test edge cases for set_config."""

    if should_fail:
        with pytest.raises(ValueError):
            await config_manager.set_config(section, key, value)
    else:
        await config_manager.set_config(section, key, value)

        # Retrieve and verify the stored value
        stored_value = await config_manager.get_config(section, key)
        if isinstance(value, (list, dict)):
            stored_value = (
                json.loads(stored_value)
                if isinstance(stored_value, str)
                else stored_value
            )

        assert stored_value == value, f"Expected {value}, got {stored_value}"


@pytest.mark.asyncio
async def test_delete_config_not_found(config_manager):
    """Test deleting a non-existent configuration raises 404."""
    with pytest.raises(HTTPException) as exc_info:
        await config_manager.delete_config("non_existent_section", "non_existent_key")

    assert exc_info.value.status_code == 404, "Expected 404 error for missing config"


@pytest.mark.asyncio
async def test_delete_full_section(config_manager):
    """Test deleting an entire section removes all keys within it."""

    section, section_data = "delete_section", {"key1": "value1", "key2": "value2"}

    # Set section
    await config_manager.set_config(section, value=section_data)

    # Delete full section
    await config_manager.delete_config(section)

    # Ensure section is removed
    result = await config_manager.get_config(section)
    assert (
        result is None or result == {}
    ), "Expected section to be completely removed from DB"


@pytest.mark.asyncio
async def test_set_config_section_without_key(config_manager):
    """Test setting a full section without a specific key."""
    section, section_data = "test_section", {"key1": "value1", "key2": "value2"}

    # Set entire section
    await config_manager.set_config(section, value=section_data)

    # Retrieve and validate
    result = await config_manager.get_config(section)
    assert isinstance(result, dict), "Expected a dictionary for the full section"
    assert result == section_data, f"Expected {section_data}, got {result}"


@pytest.mark.asyncio
async def test_get_full_section(config_manager):
    """Test retrieving an entire section."""
    section, section_data = "test_section_full", {
        "key1": "value1",
        "key2": "value2",
        "key3": "value3",
    }

    # Set full section
    await config_manager.set_config(section, value=section_data)

    # Retrieve and verify
    result = await config_manager.get_config(section)
    assert isinstance(result, dict), "Expected a dictionary for full section retrieval"
    assert result == section_data, f"Expected {section_data}, got {result}"


@pytest.mark.asyncio
async def test_get_empty_section(config_manager):
    """Test retrieving a non-existent section should return None or empty dict."""

    section = "non_existent_section"

    # Ensure empty retrieval behavior
    result = await config_manager.get_config(section)
    assert result is None or result == {}, f"Expected None or empty dict, got {result}"
