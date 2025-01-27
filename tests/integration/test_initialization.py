import json
from unittest.mock import patch, mock_open
import pytest
from sqlalchemy import text

from .db_setup import get_session_factory


@pytest.mark.asyncio
async def test_initialize_from_yaml_file(config_manager):
    """Test loading initial configuration from a YAML file."""
    yaml_content = """
    section1:
      key1: value1
      key2: value2
    section2:
      keyA: valueA
    """

    # Get a new session from the factory
    async for session in get_session_factory():
        try:
            await session.execute(
                text("DELETE FROM configuration.configurations;")
            )  # Use the correct schema
            await session.commit()
            break
        finally:
            await session.close()

    with patch("builtins.open", mock_open(read_data=yaml_content)), patch(
        "os.path.exists", return_value=True
    ):
        config_manager.input_file_path = "config.yaml"  # Mock file path
        await config_manager.initialize()

    result = await config_manager.get_config("section1", "key1")
    assert result == "value1"


@pytest.mark.asyncio
async def test_initialize_from_json_file(config_manager):
    """Test loading initial configuration from a JSON file."""
    json_content = json.dumps(
        {
            "section1": {"key1": "value1", "key2": "value2"},
            "section2": {"keyA": "valueA"},
        }
    )

    with patch("builtins.open", mock_open(read_data=json_content)), patch(
        "os.path.exists", return_value=True
    ):
        config_manager.input_file_path = "config.json"
        await config_manager.initialize()

    result = await config_manager.get_config("section1", "key2")
    assert result == "value2"


@pytest.mark.asyncio
async def test_initialize_from_toml_file(config_manager):
    """Test loading initial configuration from a TOML file."""
    toml_content = """
    [section1]
    key1 = "value1"
    key2 = "value2"
    
    [section2]
    key_a = "valueA"
    """

    # Get a new session from the factory
    async for session in get_session_factory():
        try:
            await session.execute(text("DELETE FROM configuration.configurations;"))
            await session.commit()
            break
        finally:
            await session.close()

    with patch("builtins.open", mock_open(read_data=toml_content)), patch(
        "os.path.exists", return_value=True
    ):
        config_manager.input_file_path = "config.toml"
        await config_manager.initialize()

    result = await config_manager.get_config("section2", "key_a")
    assert result == "valueA"

    async with config_manager.redis_manager.get_client(
        config_manager.redis_url
    ) as redis_client:
        print("🗑️ Manually flushing Redis after test...")
        await redis_client.flushdb()


@pytest.mark.asyncio
async def test_initialize_with_file_loading(config_manager, mocker):
    """Test that config loads from a file if the database is empty."""
    yaml_content = """
    section1:
      key1: value1
      key2: value2
    """

    # Mock DB to return no configs
    mocker.patch("unified_config.core.db_access.get_config_from_db", return_value=[])

    # Mock file reading
    mocker.patch("builtins.open", mocker.mock_open(read_data=yaml_content))
    mocker.patch("os.path.exists", return_value=True)

    config_manager.input_file_path = "config.yaml"

    await config_manager.initialize()

    result = await config_manager.get_config("section1", "key1")
    assert result == "value1", "Expected value1 from file import"
