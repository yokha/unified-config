import logging
from unittest.mock import AsyncMock, MagicMock
import pytest
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from unified_config.core.db_operation import db_operation, get_lock_timeout_sql


@pytest.mark.asyncio
async def test_db_operation_success():
    """Test that db_operation executes successfully and commits the transaction."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute.return_value = None  # Mock successful execution
    mock_session.commit.return_value = None
    mock_session.bind = MagicMock()  # Fix: Add `bind` to mock session
    mock_session.bind.dialect.name = "postgresql"  # Fix: Mock the dialect name

    mock_factory = MagicMock()
    mock_factory.return_value.__aiter__.return_value = [
        mock_session
    ]  # Async generator mock

    async def mock_db_function(session, value):
        return f"Processed {value}"

    result = await db_operation(mock_factory, mock_db_function, "test_value")

    assert result == "Processed test_value"
    mock_session.commit.assert_called_once()  # Ensure commit is called


@pytest.mark.asyncio
async def test_db_operation_integrity_error_retries():
    """Test db_operation retries on IntegrityError and eventually succeeds."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.commit.side_effect = [
        IntegrityError("mock error", orig=None, params=None),
        None,
    ]  # Fail once, then succeed
    mock_session.bind = MagicMock()
    mock_session.bind.dialect.name = "postgresql"  # Fix: Mock dialect

    mock_factory = MagicMock()
    mock_factory.return_value.__aiter__.return_value = [mock_session]

    async def mock_db_function(session, value):
        return f"Processed {value}"

    result = await db_operation(mock_factory, mock_db_function, "test_value")

    assert result == "Processed test_value"
    assert mock_session.commit.call_count == 2  # It should retry once before succeeding


@pytest.mark.asyncio
async def test_db_operation_operational_error_retries():
    """Test db_operation retries on OperationalError and eventually succeeds."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.commit.side_effect = [
        OperationalError("mock error", orig=None, params=None),
        None,
    ]
    mock_session.bind = MagicMock()
    mock_session.bind.dialect.name = "postgresql"  # Fix: Mock dialect

    mock_factory = MagicMock()
    mock_factory.return_value.__aiter__.return_value = [mock_session]

    async def mock_db_function(session, value):
        return f"Processed {value}"

    result = await db_operation(mock_factory, mock_db_function, "test_value")

    assert result == "Processed test_value"
    assert mock_session.commit.call_count == 2  # It should retry once before succeeding


@pytest.mark.asyncio
async def test_db_operation_max_retries_exceeded():
    """Test db_operation fails after exceeding max retries."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.commit.side_effect = IntegrityError(
        "mock error", orig=None, params=None
    )  # Always fail
    mock_session.bind = MagicMock()
    mock_session.bind.dialect.name = "postgresql"  # Fix: Mock dialect

    mock_factory = MagicMock()
    mock_factory.return_value.__aiter__.return_value = [mock_session]

    async def mock_db_function(session, value):
        return f"Processed {value}"

    result = await db_operation(
        mock_factory, mock_db_function, "test_value", max_retries=2
    )

    assert result is None  # Expect None after max retries
    assert mock_session.commit.call_count == 2  # Retries twice before failing


@pytest.mark.asyncio
async def test_db_operation_handles_exceptions():
    """Test db_operation handles generic exceptions correctly."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.commit.side_effect = Exception("Unexpected failure")
    mock_session.bind = MagicMock()
    mock_session.bind.dialect.name = "postgresql"  # Fix: Mock dialect

    mock_factory = MagicMock()
    mock_factory.return_value.__aiter__.return_value = [mock_session]

    async def mock_db_function(session, value):
        return f"Processed {value}"

    with pytest.raises(Exception, match="Unexpected failure"):
        await db_operation(mock_factory, mock_db_function, "test_value")


@pytest.mark.asyncio
async def test_db_operation_logs_errors(caplog):
    """Test db_operation logs errors properly when an exception occurs."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.commit.side_effect = IntegrityError(
        "mock error", orig=None, params=None
    )
    mock_session.bind = MagicMock()
    mock_session.bind.dialect.name = "postgresql"  # Fix: Mock dialect

    mock_factory = MagicMock()
    mock_factory.return_value.__aiter__.return_value = [mock_session]

    async def mock_db_function(session, value):
        return f"Processed {value}"

    with caplog.at_level(logging.ERROR):
        await db_operation(mock_factory, mock_db_function, "test_value", max_retries=1)

    # Fix: Check for a more generic failure message
    expected_log_messages = [
        "IntegrityError in mock_db_function",
        "Max retries exceeded for mock_db_function",
        "DB operation mock_db_function failed",
    ]

    assert any(
        any(expected_msg in record.message for expected_msg in expected_log_messages)
        for record in caplog.records
    ), f"Expected one of {expected_log_messages} in logs, but got: {[record.message for record in caplog.records]}"


@pytest.mark.asyncio
async def test_get_lock_timeout_sql():
    """Test that get_lock_timeout_sql returns correct SQL for each dialect."""
    mock_session_postgres = MagicMock()
    mock_session_postgres.bind = MagicMock()  # Fix: Add `bind`
    mock_session_postgres.bind.dialect.name = "postgresql"
    assert (
        get_lock_timeout_sql(mock_session_postgres, 5000)
        == "SET LOCAL lock_timeout = 5000"
    )

    mock_session_mysql = MagicMock()
    mock_session_mysql.bind = MagicMock()
    mock_session_mysql.bind.dialect.name = "mysql"
    assert (
        get_lock_timeout_sql(mock_session_mysql, 5000)
        == "SET innodb_lock_wait_timeout = 5"
    )

    mock_session_sqlite = MagicMock()
    mock_session_sqlite.bind = MagicMock()
    mock_session_sqlite.bind.dialect.name = "sqlite"
    assert get_lock_timeout_sql(mock_session_sqlite, 5000) is None
