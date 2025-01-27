import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import IntegrityError
from sqlalchemy import Column, String, Integer, Text
from unified_config.core.db_access import (
    get_config_from_db,
    set_config_in_db,
    delete_config_from_db,
    _upsert_config,
    fetch_config_history_from_db,
    get_all_configs_from_db,
)
from unified_config.core.schemas import ConfigValue
from unified_config.models.db_model import ConfigModel, ConfigHistoryModel


Base = declarative_base()


class MockConfigModel(Base):
    """Represents a mock database model for storing configuration settings."""

    __tablename__ = "config"

    id = Column(Integer, primary_key=True, autoincrement=True)  # Primary key
    section = Column(String, nullable=False)
    key = Column(String, nullable=False)
    value = Column(Text, nullable=False)  # Store JSON values as text


@pytest.fixture
def mock_db_session():
    """Fixture to provide a properly mocked AsyncSession."""
    session = AsyncMock(spec=AsyncSession)
    session.execute.return_value = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_get_config_from_db(mock_db_session):
    """Test fetching configuration from DB."""
    mock_model_instance = MagicMock(spec=ConfigModel)
    mock_model_instance.value = json.dumps({"key": "mocked_value"})

    mock_scalars_result = MagicMock()
    mock_scalars_result.all.return_value = [mock_model_instance]

    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars_result
    mock_db_session.execute.return_value = mock_result

    result = await get_config_from_db(
        mock_db_session, ConfigModel, section="test_section", key="test_key"
    )

    assert result == {"key": "mocked_value"}


@pytest.mark.asyncio
async def test_get_config_from_db_not_found(mock_db_session: AsyncMock):
    """Test fetching a non-existing config returns None."""

    # Use MagicMock for `.all()`, AsyncMock only for async methods
    mock_scalars_result = MagicMock()
    mock_scalars_result.all.return_value = []  # Regular method, no need for `AsyncMock`

    mock_result = MagicMock()
    mock_result.scalars.return_value = (
        mock_scalars_result  # Ensure scalars() is awaited
    )
    mock_db_session.execute.return_value = mock_result

    result = await get_config_from_db(
        mock_db_session, ConfigModel, section="non_existing"
    )

    assert result is None
    mock_db_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_set_config_in_db(mock_db_session):
    """Test setting a new configuration in DB."""
    mock_db_session.merge = AsyncMock()  # Mock `merge()`

    await set_config_in_db(
        mock_db_session,
        ConfigModel,
        "test_section",
        "test_key",
        ConfigValue(value="new_value"),
    )

    mock_db_session.merge.assert_called()  # Ensure `merge()` was called


@pytest.mark.asyncio
async def test_set_config_in_db_invalid_data(mock_db_session):
    """Test setting an invalid config raises ValueError."""

    # `None` should still raise an error (invalid case)
    with pytest.raises(ValueError) as exc_info:
        await set_config_in_db(
            mock_db_session, MockConfigModel, "test_section", None, None
        )

    assert (
        "Configuration section must be a dictionary, list, or a primitive value"
        in str(exc_info.value)
    )

    # Now valid cases (str, int, float, bool) should NOT raise errors
    valid_values = ["string_value", 42, 3.14, True]

    for value in valid_values:
        try:
            await set_config_in_db(
                mock_db_session, MockConfigModel, "test_section", None, value
            )
        except ValueError:
            pytest.fail(f"Unexpected ValueError for valid value: {value}")


@pytest.mark.asyncio
async def test_delete_config_from_db(mock_db_session):
    """Test deleting a configuration from DB."""
    mock_db_session.execute.return_value.rowcount = 1  # Simulate successful deletion

    result = await delete_config_from_db(
        mock_db_session, ConfigModel, "test_section", "test_key"
    )

    assert result is True  # Ensure deletion was successful


@pytest.mark.asyncio
async def test_delete_config_from_db_no_match(mock_db_session):
    """Test deleting a non-existing config."""
    mock_db_session.execute.return_value.rowcount = 0  # Simulate no deletion

    result = await delete_config_from_db(
        mock_db_session, ConfigModel, "test_section", "missing_key"
    )

    assert result is False  # No deletion happened


@pytest.mark.asyncio
async def test_delete_config_from_db_full_section(mock_db_session):
    """Test deleting an entire section."""
    mock_db_session.execute.return_value.rowcount = 5  # Assume 5 records deleted

    result = await delete_config_from_db(mock_db_session, ConfigModel, "test_section")

    assert result is True  # Deletion successful


@pytest.mark.asyncio
async def test_delete_config_from_db_rollback_on_failure(mock_db_session):
    """Test rollback on delete failure (no longer applicable)."""
    mock_db_session.execute.side_effect = Exception("Delete error")

    with pytest.raises(Exception, match="Delete error"):
        await delete_config_from_db(
            mock_db_session, ConfigModel, "test_section", "test_key"
        )


@pytest.mark.asyncio
async def test_set_config_in_db_empty_value(mock_db_session):
    """Test setting an empty string as a config value."""
    mock_db_session.merge = AsyncMock()

    await set_config_in_db(
        mock_db_session, ConfigModel, "test_section", "test_key", ConfigValue(value="")
    )

    mock_db_session.merge.assert_called()  # Ensure merge() was called


@pytest.mark.asyncio
async def test_get_config_from_db_db_failure(mock_db_session):
    """Test handling database failure during config retrieval."""
    mock_db_session.execute.side_effect = Exception(
        "Database failure"
    )  # Simulate DB failure

    with pytest.raises(Exception, match="Database failure"):
        await get_config_from_db(mock_db_session, ConfigModel, section="test_section")


@pytest.mark.asyncio
async def test_get_config_from_db_invalid_model(mock_db_session):
    """Test get_config_from_db when model is None."""
    result = await get_config_from_db(mock_db_session, None, section="test_section")
    assert result is None  # Expecting early return


@pytest.mark.asyncio
async def test_get_config_from_db_without_section(mock_db_session):
    """Test fetching a config where section is missing but key exists."""
    mock_model_instance = MagicMock(spec=ConfigModel)
    mock_model_instance.section = "mock_section"  # Mock section value
    mock_model_instance.key = "test_key"  # Mock key value
    mock_model_instance.value = json.dumps("value_without_section")

    mock_scalars_result = MagicMock()
    mock_scalars_result.all.return_value = [mock_model_instance]  # Simulate DB return

    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars_result
    mock_db_session.execute.return_value = mock_result

    result = await get_config_from_db(mock_db_session, ConfigModel, key="test_key")

    expected_result = [
        {"section": "mock_section", "key": "test_key", "value": "value_without_section"}
    ]  # Match the function's return format

    assert (
        result == expected_result
    )  # Adjust assertion to expect a list of dictionaries


@pytest.mark.asyncio
async def test_set_config_in_db_rollback_on_failure(mock_db_session):
    """Test rollback on set_config_in_db failure (no longer applicable)."""
    mock_db_session.merge.side_effect = Exception("Insert failed")

    with pytest.raises(Exception, match="Insert failed"):
        await set_config_in_db(
            mock_db_session,
            ConfigModel,
            "test_section",
            "test_key",
            ConfigValue(value="test_value"),
        )


@pytest.mark.asyncio
async def test_get_config_from_db_invalid_json(mock_db_session):
    """Test handling of invalid JSON in config value."""
    mock_model_instance = MagicMock(spec=ConfigModel)
    mock_model_instance.value = "{invalid_json"  # Corrupt JSON

    mock_scalars_result = MagicMock()
    mock_scalars_result.all.return_value = [mock_model_instance]

    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars_result
    mock_db_session.execute.return_value = mock_result

    result = await get_config_from_db(
        mock_db_session, ConfigModel, section="test_section", key="test_key"
    )

    assert result == "{invalid_json"  # Should return raw string if JSON parsing fails


@pytest.mark.asyncio
async def test_get_all_configs_from_db(mock_db_session):
    """Test fetching all configs from an empty DB (fixing None return)."""
    mock_scalars_result = MagicMock()
    mock_scalars_result.all.return_value = []
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars_result
    mock_db_session.execute.return_value = mock_result

    result = await get_all_configs_from_db(mock_db_session, ConfigModel)

    assert result == {}  # Ensure an empty dictionary is returned instead of None.


@pytest.mark.asyncio
async def test_upsert_config_integrity_error(mock_db_session):
    """Test _upsert_config handles IntegrityError."""
    mock_db_session.merge.side_effect = IntegrityError("Duplicate entry", None, None)

    with pytest.raises(IntegrityError, match="Duplicate entry"):
        await _upsert_config(
            mock_db_session, ConfigModel, "test_section", "test_key", "test_value"
        )

    assert mock_db_session.merge.call_count == 1  # No retries expected


@pytest.mark.asyncio
async def test_upsert_config_no_retry_on_integrity_error(mock_db_session):
    """Test _upsert_config does not retry on IntegrityError."""
    mock_db_session.merge.side_effect = IntegrityError("Duplicate entry", None, None)

    with pytest.raises(IntegrityError, match="Duplicate entry"):
        await _upsert_config(
            mock_db_session, ConfigModel, "test_section", "test_key", "test_value"
        )

    assert mock_db_session.merge.call_count == 1  # Ensure no retry happened


@pytest.mark.asyncio
async def test_upsert_config_generic_error(mock_db_session):
    """Test _upsert_config handles generic exceptions."""
    mock_db_session.merge.side_effect = Exception("Unexpected DB error")

    with pytest.raises(Exception, match="Unexpected DB error"):
        await _upsert_config(
            mock_db_session, ConfigModel, "test_section", "test_key", "test_value"
        )

    assert mock_db_session.merge.call_count == 1  # No retries for generic errors


@pytest.mark.asyncio
async def test_fetch_config_history_pagination(mock_db_session):
    """Test pagination of config history."""
    mock_model_instance = MagicMock(spec=ConfigHistoryModel)
    mock_model_instance.section = "history_section"
    mock_model_instance.key = "history_key"
    mock_model_instance.new_value = json.dumps("value")
    mock_model_instance.timestamp = datetime.now()

    mock_scalars_result = MagicMock()
    mock_scalars_result.all.return_value = [mock_model_instance]

    mock_result = MagicMock()
    mock_result.scalar.return_value = 5  # Mock total_count as an integer
    mock_result.scalars.return_value = mock_scalars_result
    mock_db_session.execute.return_value = mock_result  # Mock database execution

    result = await fetch_config_history_from_db(
        mock_db_session, ConfigHistoryModel, limit=1, offset=0
    )

    assert result["total_count"] > 0  # Now it correctly compares an int
    assert len(result["data"]) == 1  # Ensuring pagination works


@pytest.mark.asyncio
async def test_upsert_config_retries_on_integrity_error(mock_db_session):
    """Test that the caller of `_upsert_config` should handle IntegrityError retries."""
    mock_db_session.merge.side_effect = IntegrityError("Duplicate entry", None, None)

    # First attempt should fail with IntegrityError
    with pytest.raises(IntegrityError, match="Duplicate entry"):
        await _upsert_config(
            mock_db_session, ConfigModel, "test_section", "test_key", "test_value"
        )

    # Ensure it was only attempted once (no internal retry)
    assert (
        mock_db_session.merge.call_count == 1
    ), "Merge should have been called exactly once"


@pytest.mark.asyncio
async def test_delete_config_from_db_no_matching_section(mock_db_session):
    """Test deleting a non-existent section does nothing."""
    mock_db_session.execute.return_value.rowcount = 0  # Simulate no deletions

    result = await delete_config_from_db(
        mock_db_session, ConfigModel, "non_existing_section"
    )

    assert result is False  # Should return False


@pytest.mark.asyncio
async def test_set_config_in_db_invalid_value(mock_db_session):
    """Test set_config_in_db raises ValueError for invalid data types."""
    with pytest.raises(ValueError):
        await set_config_in_db(
            mock_db_session, ConfigModel, "test_section", "test_key", object()
        )  # Invalid type


@pytest.mark.asyncio
async def test_fetch_config_history_empty_db(mock_db_session):
    """Test fetching history when DB has no entries."""
    mock_result = MagicMock()
    mock_result.scalar.return_value = 0  # No total count
    mock_result.scalars.return_value.all.return_value = []  # Empty history data

    mock_db_session.execute.return_value = mock_result

    result = await fetch_config_history_from_db(
        mock_db_session, ConfigHistoryModel, limit=5, offset=0
    )

    assert result["total_count"] == 0  # Should be 0
    assert result["data"] == []  # Should be empty


@pytest.mark.asyncio
async def test_get_config_from_db_list_section(mock_db_session):
    """Test that `get_config_from_db` restores lists stored as `__list__`."""
    mock_model_instance = MagicMock(spec=ConfigModel)
    mock_model_instance.key = "__list__"
    mock_model_instance.value = json.dumps(
        ["item1", "item2"]
    )  # Simulate DB-stored list
    mock_model_instance.section = "list_section"

    mock_scalars_result = MagicMock()
    mock_scalars_result.all.return_value = [mock_model_instance]  # Simulate DB return

    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars_result
    mock_db_session.execute.return_value = mock_result

    result = await get_config_from_db(
        mock_db_session, ConfigModel, section="list_section"
    )

    assert result == [
        "item1",
        "item2",
    ], "Expected `__list__` key to be restored as a list."


@pytest.mark.asyncio
async def test_get_all_configs_from_db_list_section(mock_db_session):
    """Test `get_all_configs_from_db` converts `__list__` back to a list in the exported config."""
    mock_model_instance1 = MagicMock(spec=ConfigModel)
    mock_model_instance1.section = "list_section"
    mock_model_instance1.key = "__list__"
    mock_model_instance1.value = json.dumps(["item1", "item2"])

    mock_model_instance2 = MagicMock(spec=ConfigModel)
    mock_model_instance2.section = "regular_section"
    mock_model_instance2.key = "key1"
    mock_model_instance2.value = json.dumps("value1")

    mock_scalars_result = MagicMock()
    mock_scalars_result.all.return_value = [
        mock_model_instance1,
        mock_model_instance2,
    ]  # Simulating DB return

    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars_result
    mock_db_session.execute.return_value = mock_result

    result = await get_all_configs_from_db(mock_db_session, ConfigModel)

    expected_result = {
        "list_section": ["item1", "item2"],  # `__list__` converted to list
        "regular_section": {"key1": "value1"},  # Other sections remain unchanged
    }

    assert (
        result == expected_result
    ), "Expected `__list__` sections to be converted to lists."
