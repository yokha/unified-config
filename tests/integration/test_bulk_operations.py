import json
import pytest

from .conftest import REDIS_URL


@pytest.mark.asyncio
async def test_set_and_get_bulk_config(config_manager):
    """Test setting and retrieving multiple configurations in bulk."""
    configs = {
        "database": {
            "host": "localhost",
            "port": 5432,
        },
        "app_settings": {
            "theme": "dark",
            "language": "en",
        },
    }

    # Set bulk configs
    await config_manager.set_bulk_config(configs, updated_by="test_user")

    # Fetch bulk configs
    retrieved_configs = await config_manager.get_bulk_config(
        ["database", "app_settings"]
    )

    assert retrieved_configs["database"]["host"] == "localhost"
    assert retrieved_configs["database"]["port"] == 5432
    assert retrieved_configs["app_settings"]["theme"] == "dark"
    assert retrieved_configs["app_settings"]["language"] == "en"


@pytest.mark.asyncio
async def test_get_bulk_config_with_caching(config_manager, redis_client):
    """Test fetching multiple configs in bulk and ensuring Redis caching."""
    await config_manager.set_config("bulk_section1", "key1", "value1")
    await config_manager.set_config("bulk_section2", "key2", "value2")

    sections = ["bulk_section1", "bulk_section2"]
    results = await config_manager.get_bulk_config(sections)

    assert (
        results["bulk_section1"]["key1"] == "value1"
    ), "Expected value1 from bulk fetch"
    assert (
        results["bulk_section2"]["key2"] == "value2"
    ), "Expected value2 from bulk fetch"

    # Ensure they are cached in Redis
    async with redis_client.get_client(REDIS_URL) as client:
        cached_value = await client.get("bulk_section1")
        assert (
            json.loads(cached_value)["key1"] == "value1"
        ), "Expected Redis cache to be set"


@pytest.mark.asyncio
async def test_get_config_sections_using_bulk(config_manager):
    """Ensure retrieving all config sections indirectly works via get_bulk_config()."""

    # Step 1: Set configs in multiple sections
    await config_manager.set_config("section1", "key1", "value1")
    await config_manager.set_config("section2", "key2", "value2")

    # Step 2: Use get_bulk_config() to fetch sections
    bulk_data = await config_manager.get_bulk_config(["section1", "section2"])

    # Step 3: Extract sections from the response and verify
    retrieved_sections = set(bulk_data.keys())  # Convert to set for comparison
    expected_sections = {"section1", "section2"}

    assert (
        retrieved_sections == expected_sections
    ), f"Expected sections {expected_sections}, got {retrieved_sections}"


@pytest.mark.asyncio
async def test_bulk_set_get_config(config_manager, redis_client):
    """Ensure bulk setting and retrieving configurations works correctly."""

    # Step 1: Define bulk configs in the expected format
    configs = {
        "bulk_test_section1": {
            "key1": "value1",
            "key2": 42,
            "key3": 3.14,
        },
        "bulk_test_section2": {
            "key_a": True,
            "key_b": ["list", "values"],
        },
    }

    # Step 2: Bulk set configs
    await config_manager.set_bulk_config(configs)

    # Step 3: Retrieve and verify each section
    for section, keys in configs.items():
        retrieved_configs = await config_manager.get_config(section)

        assert (
            retrieved_configs is not None
        ), f"Expected configs to be retrieved for {section}"

        for key, expected_value in keys.items():
            assert (
                retrieved_configs[key] == expected_value
            ), f"Unexpected value for {section}.{key}: {retrieved_configs[key]}"
