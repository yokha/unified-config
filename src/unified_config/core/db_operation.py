import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.sql import text

logger = logging.getLogger(__name__)


async def db_operation(
    db_session_factory: callable,
    operation: callable,  # Pass the db_access function
    *args,
    max_retries: int = 3,
    retry_delay: float = 0.1,
    lock_timeout: int = 5000,  # Lock timeout in milliseconds
    **kwargs,
):
    """
    Handles atomic execution of a database operation with retry, lock timeout, and transaction control.

    Args:
        db_session_factory (Callable): Factory function to create a new DB session.
        operation (Callable): The database function to execute.
        *args: Positional arguments for the operation.
        max_retries (int): Maximum number of retries on failure.
        retry_delay (float): Delay between retries.
        lock_timeout (int): Timeout for DB locks (milliseconds).
        **kwargs: Additional keyword arguments.

    Returns:
        Any: The result of the operation.
    """
    operation_name = (
        operation.__name__ if hasattr(operation, "__name__") else str(operation)
    )
    logger.info(
        f"🔹 Starting DB operation: {operation_name} with args={args}, kwargs={kwargs}"
    )

    async for session in db_session_factory():
        try:
            for attempt in range(max_retries):
                try:
                    # Ensure lock timeout is set at the session level
                    lock_timeout_sql = get_lock_timeout_sql(session, lock_timeout)
                    if lock_timeout_sql:
                        await session.execute(text(lock_timeout_sql))

                    logger.info(
                        f"🔄 Attempt {attempt}/{max_retries} for {operation_name}"
                    )

                    # Call the actual DB function (without commit)
                    result = await operation(session, *args, **kwargs)

                    await session.commit()  # Commit at this level (atomicity)
                    return result

                except IntegrityError as e:
                    await session.rollback()
                    logger.warning(
                        f"⚠️ IntegrityError in {operation_name} (attempt {attempt}/{max_retries}): {e}"
                    )
                    await asyncio.sleep(retry_delay)

                except OperationalError as e:
                    await session.rollback()
                    logger.warning(
                        f"⚠️ OperationalError in {operation_name} (attempt {attempt}/{max_retries}): {e}"
                    )
                    await asyncio.sleep(retry_delay)

                except Exception as e:
                    await session.rollback()
                    logger.error(f"❌ DB operation {operation_name} failed: {e}")
                    raise

            logger.error(
                f"❌ Max retries exceeded for {operation_name}. Operation failed."
            )
            return None  # If all retries fail, return None

        finally:
            await session.close()  # Always close the session properly
            logger.info(f"🔻 DB operation {operation_name} completed. Session closed.")


def get_lock_timeout_sql(session: AsyncSession, lock_timeout: int) -> str:
    """
    Generate a database-specific SQL statement for setting lock timeout.

    Args:
        session (AsyncSession): The current SQLAlchemy session.
        lock_timeout (int): The lock timeout in milliseconds.

    Returns:
        str: A valid lock timeout SQL command based on the DB type.
    """
    dialect = session.bind.dialect.name  # Detect the database type

    if dialect == "postgresql":
        return f"SET LOCAL lock_timeout = {lock_timeout}"
    if dialect == "mysql":
        return f"SET innodb_lock_wait_timeout = {lock_timeout // 1000}"  # Convert to seconds
    if dialect == "sqlite":
        return None  # SQLite does not support lock timeouts
    return None  # Unsupported DB
