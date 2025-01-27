import logging
from unittest.mock import AsyncMock, MagicMock, PropertyMock
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import OperationalError
from unified_config.core.db_operation import db_operation

logger = logging.getLogger(__name__)


def mock_session_factory():
    """Create a properly mocked session factory with dialect handling."""
    mock_session = AsyncMock(spec=AsyncSession)

    # Fix: Properly mock `session.bind.dialect.name`
    mock_bind = MagicMock()
    type(mock_bind).dialect = PropertyMock(return_value=MagicMock(name="postgresql"))
    mock_session.bind = mock_bind

    return mock_session


@pytest.mark.asyncio
async def test_db_operation_deadlock_with_retries(caplog):
    """Test db_operation retries correctly when a deadlock occurs."""
    mock_session = mock_session_factory()
    mock_session.execute.side_effect = [
        OperationalError("deadlock detected", orig=None, params=None),
        None,
    ]
    mock_session.commit.side_effect = [
        OperationalError("deadlock detected", orig=None, params=None),
        None,
    ]

    mock_factory = MagicMock()
    mock_factory.return_value.__aiter__.return_value = [mock_session]

    async def mock_db_function(session, value):
        return f"Processed {value}"

    with caplog.at_level(logging.WARNING):
        result = await db_operation(
            mock_factory, mock_db_function, "test_value", max_retries=3
        )

    assert (
        result == "Processed test_value"
    ), "Expected db_operation to succeed after retries"
    assert (
        sum("deadlock detected" in record.message.lower() for record in caplog.records)
        >= 1
    ), "Expected deadlock warnings to be logged."


@pytest.mark.asyncio
async def test_db_operation_deadlock_max_retries_exceeded(caplog):
    """Test db_operation fails after exceeding max retries on deadlock."""
    mock_session = mock_session_factory()
    mock_session.execute.side_effect = OperationalError(
        "deadlock detected", orig=None, params=None
    )
    mock_session.commit.side_effect = OperationalError(
        "deadlock detected", orig=None, params=None
    )

    mock_factory = MagicMock()
    mock_factory.return_value.__aiter__.return_value = [mock_session]

    async def mock_db_function(session, value):
        return f"Processed {value}"

    with caplog.at_level(logging.ERROR):
        result = await db_operation(
            mock_factory, mock_db_function, "test_value", max_retries=3
        )

    assert (
        result is None
    ), "Expected db_operation to return None after max retries exceeded"
    assert any(
        "Max retries exceeded" in record.message for record in caplog.records
    ), "Expected 'Max retries exceeded' log message."


@pytest.mark.asyncio
async def test_db_operation_async_deadlock_with_retry_success(caplog):
    """Test db_operation resolves deadlocks in a single-threaded async scenario with retries."""
    mock_session = mock_session_factory()
    mock_session.execute.side_effect = [
        OperationalError("deadlock detected", orig=None, params=None),
        None,
    ]
    mock_session.commit.side_effect = [
        OperationalError("deadlock detected", orig=None, params=None),
        None,
    ]

    mock_factory = MagicMock()
    mock_factory.return_value.__aiter__.return_value = [mock_session]

    async def mock_db_function(session, value):
        return f"Processed {value}"

    with caplog.at_level(logging.WARNING):
        result = await db_operation(
            mock_factory, mock_db_function, "test_value", max_retries=3
        )

    assert (
        result == "Processed test_value"
    ), "Expected db_operation to resolve deadlock after retrying"
    assert any(
        "deadlock detected" in record.message.lower() for record in caplog.records
    ), "Expected deadlock detection logs."
