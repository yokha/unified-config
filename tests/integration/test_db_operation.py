import logging
import json
import pytest
from sqlalchemy.sql import text
from sqlalchemy.exc import OperationalError

from unified_config.core.db_operation import db_operation
from unified_config.models.db_model import ConfigModel
from unified_config.core.db_access import safe_json_loads
from .db_setup import get_session_factory


@pytest.mark.asyncio
async def test_db_operation_insert():
    """Test db_operation correctly inserts data into the database."""

    async def insert_data(session, section, key, value):
        obj = ConfigModel(section=section, key=key, value=value)
        session.add(obj)
        return obj

    _ = await db_operation(
        get_session_factory, insert_data, "test_section", "test_key", "test_value"
    )

    # Verify data exists in the database
    async for session in get_session_factory():
        stmt = await session.execute(
            text(
                "SELECT value FROM configuration.configurations WHERE section='test_section' AND key='test_key'"
            )
        )
        row = stmt.fetchone()
        assert row is not None
        assert row[0] == "test_value"
        await session.close()


@pytest.mark.asyncio
async def test_db_operation_update():
    """Test db_operation correctly updates an existing record."""

    async def update_data(session, section, key, value):
        stmt = text(
            "UPDATE configuration.configurations SET value=:value WHERE section=:section AND key=:key"
        )
        await session.execute(
            stmt, {"section": section, "key": key, "value": json.dumps(value)}
        )

    # Insert initial valid JSON data
    async for session in get_session_factory():
        await session.execute(
            text(
                "INSERT INTO configuration.configurations (section, key, value) VALUES (:section, :key, :value)"
            ),
            {
                "section": "update_section",
                "key": "update_key",
                "value": json.dumps("old_value"),
            },
        )
        await session.commit()
        break

    # Perform the update operation
    await db_operation(
        get_session_factory, update_data, "update_section", "update_key", "new_value"
    )

    # Verify the update in the database
    async for session in get_session_factory():
        stmt = await session.execute(
            text(
                "SELECT value FROM configuration.configurations WHERE section='update_section' AND key='update_key'"
            )
        )
        row = stmt.fetchone()
        assert row is not None, "❌ Expected row to exist but got None."

        retrieved_value = safe_json_loads(row[0])

        assert (
            retrieved_value == "new_value"
        ), f"❌ Expected 'new_value', but got {row[0]}"
        await session.close()


@pytest.mark.asyncio
async def test_db_operation_delete():
    """Test db_operation correctly deletes an existing record."""

    async def delete_data(session, section, key):
        stmt = text(
            "DELETE FROM configuration.configurations WHERE section=:section AND key=:key"
        )
        await session.execute(stmt, {"section": section, "key": key})

    # Insert initial valid JSON data
    async for session in get_session_factory():
        await session.execute(
            text(
                "INSERT INTO configuration.configurations (section, key, value) VALUES (:section, :key, :value)"
            ),
            {
                "section": "delete_section",
                "key": "delete_key",
                "value": json.dumps("to_delete"),
            },
        )
        await session.commit()
        break

    # Perform the delete operation
    await db_operation(get_session_factory, delete_data, "delete_section", "delete_key")

    # Verify deletion in the database
    async for session in get_session_factory():
        stmt = await session.execute(
            text(
                "SELECT value FROM configuration.configurations WHERE section='delete_section' AND key='delete_key'"
            )
        )
        row = stmt.fetchone()

        assert row is None, f"❌ Expected row to be deleted, but got {row}"


@pytest.mark.asyncio
async def test_db_operation_deadlock_handling():
    """Test db_operation properly handles and retries deadlocks."""

    async def deadlock_simulation(session, section, key, value):
        stmt = text(
            "UPDATE configuration.configurations SET value=:value WHERE section=:section AND key=:key"
        )
        await session.execute(
            stmt, {"section": section, "key": key, "value": json.dumps(value)}
        )

    # Insert initial valid JSON data
    async for session in get_session_factory():
        await session.execute(
            text(
                "INSERT INTO configuration.configurations (section, key, value) VALUES (:section, :key, :value)"
            ),
            {
                "section": "deadlock_section",
                "key": "deadlock_key",
                "value": json.dumps("old_value"),
            },
        )
        await session.commit()
        break

    # Simulate a deadlock by forcing an exception on the first attempt
    retry_counter = 0

    async def faulty_operation(session, section, key, value):
        nonlocal retry_counter
        retry_counter += 1
        if retry_counter == 1:  # Simulate deadlock **only** on first try
            raise OperationalError("Deadlock detected", None, None)

        await deadlock_simulation(session, section, key, value)  # Perform real update

    # Perform the operation with expected retry
    await db_operation(
        get_session_factory,
        faulty_operation,
        "deadlock_section",
        "deadlock_key",
        "new_value",
    )

    # Ensure it retried correctly
    assert retry_counter > 1, "❌ Deadlock retry mechanism did not trigger!"

    # Verify final value in DB
    async for session in get_session_factory():
        stmt = await session.execute(
            text(
                "SELECT value FROM configuration.configurations WHERE section='deadlock_section' AND key='deadlock_key'"
            )
        )
        row = stmt.fetchone()
        assert row is not None, "❌ Expected row to exist after retry."
        assert (
            safe_json_loads(row[0]) == "new_value"
        ), f"❌ Expected 'new_value', but got {row[0]}"


@pytest.mark.asyncio
async def test_db_operation_integrity_error(caplog):
    """Test db_operation properly handles IntegrityErrors and logs them instead of retrying indefinitely."""

    async def insert_duplicate(session, section, key, value):
        stmt = text(
            "INSERT INTO configuration.configurations (section, key, value) VALUES (:section, :key, :value)"
        )
        await session.execute(
            stmt, {"section": section, "key": key, "value": json.dumps(value)}
        )

    # Insert initial valid JSON data
    async for session in get_session_factory():
        await session.execute(
            text(
                "INSERT INTO configuration.configurations (section, key, value) VALUES (:section, :key, :value)"
            ),
            {
                "section": "integrity_section",
                "key": "duplicate_key",
                "value": json.dumps("original_value"),
            },
        )
        await session.commit()
        break

    # Capture logs while running db_operation
    with caplog.at_level(logging.WARNING):
        await db_operation(
            get_session_factory,
            insert_duplicate,
            "integrity_section",
            "duplicate_key",
            "new_value",
        )

    # Assert that the IntegrityError log appears
    assert "IntegrityError in insert_duplicate" in caplog.text


@pytest.mark.asyncio
async def test_db_operation_retries_and_succeeds(caplog):
    """Test db_operation retries and eventually succeeds after a transient failure."""

    attempt_counter = 0

    async def flaky_insert(session, section, key, value):
        """Simulate transient failure on the first attempt."""
        nonlocal attempt_counter
        attempt_counter += 1

        if attempt_counter == 1:  # Simulate failure on the first attempt
            raise OperationalError("Simulated transient failure", None, None)

        # Second attempt succeeds
        stmt = text(
            "INSERT INTO configuration.configurations (section, key, value) VALUES (:section, :key, :value)"
        )
        await session.execute(
            stmt, {"section": section, "key": key, "value": json.dumps(value)}
        )

    with caplog.at_level(logging.WARNING):
        await db_operation(
            get_session_factory,
            flaky_insert,
            "retry_section",
            "retry_key",
            "retry_value",
        )

    # Ensure a warning was logged for the failure
    assert "Simulated transient failure" in caplog.text

    # Verify the entry was successfully inserted after the retry
    async for session in get_session_factory():
        stmt = await session.execute(
            text(
                "SELECT value FROM configuration.configurations WHERE section='retry_section' AND key='retry_key'"
            )
        )
        row = stmt.fetchone()
        assert row is not None, "❌ Expected row to exist after retry, but got None."
        assert (
            safe_json_loads(row[0]) == "retry_value"
        ), f"❌ Expected 'retry_value', but got {row[0]}"
