from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
# Import your database connection and metadata
from database import DATABASE_URL, metadata_config, metadata_function

# Alembic Config object
config = context.config
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Define metadata for both schemas
target_metadata = [metadata_config, metadata_function]

# Configure logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        include_schemas=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = create_async_engine(DATABASE_URL, poolclass=pool.NullPool, echo=True)

    async def do_migrations():
        async with connectable.begin() as conn:
            await conn.run_sync(
                lambda sync_conn: context.configure(  # Fix: Use lambda to prevent duplicate args
                    connection=sync_conn,
                    target_metadata=target_metadata,
                    include_schemas=True,
                )
            )
            await conn.run_sync(
                lambda _: context.run_migrations()
            )  # Fix: Prevent extra argument error

    import asyncio

    asyncio.run(do_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
