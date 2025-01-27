import os
import json
import asyncio
from typing import Union, Dict, List, Any, Callable
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy.orm import DeclarativeMeta
from redis_manager.redis_manager import RedisManager
from unified_config.core.db_access import (
    get_config_from_db,
    set_config_in_db,
    delete_config_from_db,
    get_all_configs_from_db,
    fetch_config_history_from_db,
    set_config_history,
    _upsert_config,
    safe_json_loads,
)
from unified_config.core.db_operation import db_operation
from unified_config.core.schemas import (
    ConfigEntry,
    ConfigSection,
    ConfigValue,
)  # Pydantic validation models
from unified_config.core.data_conversion import load_config_file
from unified_config.core.data_conversion import convert_config

from unified_config.core.logger import logger


async def retry_redis_operation(
    operation: Callable[[], Any],
    max_retries: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
) -> Union[bool, None]:
    """Retries a Redis operation with exponential backoff."""
    attempt = 0
    while attempt < max_retries:
        try:
            return await operation()
        except Exception as e:
            attempt += 1
            logger.warning(
                f"Redis operation failed (attempt {attempt}/{max_retries}): {e}"
            )
            await asyncio.sleep(delay)
            delay *= backoff_factor
    logger.error("Redis operation failed after max retries.")
    return None


class ConfigManager:
    """
    Manages configurations stored in a database and Redis.
    """

    def __init__(
        self,
        redis_url: str,
        db_session_factory: callable,
        config_model: DeclarativeMeta,
        config_history_model: DeclarativeMeta,
        redis_manager: Union[RedisManager, None] = None,
        redis_config: Union[Dict[str, Any], None] = None,
        input_file_path: Union[str, None] = None,
    ) -> None:
        self.redis_url: str = redis_url
        self.db_session_factory = db_session_factory
        self.config_model: DeclarativeMeta = config_model
        self.config_history_model: DeclarativeMeta = config_history_model
        self.input_file_path: Union[str, None] = input_file_path

        if redis_manager:
            self.redis_manager: RedisManager = redis_manager
        else:
            redis_config = redis_config or {}
            self.redis_manager: RedisManager = RedisManager(**redis_config)

        self.subscriber_task: Union[asyncio.Task, None] = None

    async def _get_session(self):
        """Helper method to get a session."""
        async for session in self.db_session_factory():
            try:
                yield session
            finally:
                await session.close()

    async def initialize(
        self, config_change_callback: Callable[[dict], None] = None
    ) -> None:
        """
        Initialize the ConfigManager by setting up Redis, loading configurations, and starting the listener.

        Args:
            config_change_callback (Callable[[dict], None]): Optional function to handle config changes.
        """
        logger.info("Initializing ConfigManager...")
        await self.redis_manager.add_node_pool(self.redis_url)
        self.redis_manager.start_cleanup()

        # Fetch configurations from the database
        logger.info("Fetching configs from DB...")

        async def fetch_configs(session):
            return await get_config_from_db(session, self.config_model, section=None)

        configs = await db_operation(self.db_session_factory, fetch_configs)

        logger.info(f"Fetched configs from DB: {configs}")

        if not configs:
            configs = []

        for config in configs:
            section = config.get("section")
            key = config.get("key")
            value = config.get("value")

            cache_key = f"{section}:{key}"
            async with self.redis_manager.get_client(self.redis_url) as redis_client:
                await redis_client.set(cache_key, json.dumps(value))

        # Load defaults from file if DB is empty
        if (
            not configs
            and self.input_file_path
            and os.path.exists(self.input_file_path)
        ):
            try:
                default_configs = load_config_file(self.input_file_path)
                if not isinstance(default_configs, (dict, list)):
                    raise ValueError(
                        "Invalid config format: Must be a dictionary or list."
                    )

                for section, values in default_configs.items():
                    await self.set_config(section, value=values)

            except ValueError as e:
                logger.error(f"Failed to load config file: {e}")

        # Start the config change listener with a callback if provided
        if self.subscriber_task:
            self.subscriber_task.cancel()
        self.subscriber_task = asyncio.create_task(
            self.listen_to_config_changes(config_change_callback)
        )
        logger.info("ConfigManager initialized.")

    async def set_config(
        self,
        section: str,
        key: Union[str, None] = None,
        value: Any = None,
        updated_by: str = "system",
    ) -> None:
        """Set or update a configuration in the DB and Redis."""

        async def db_transaction(session):
            timestamp = datetime.now(tz=timezone.utc).isoformat()
            history_entries = []  # Collect updates before logging history

            if key is None:
                # DELETE old entries before inserting new ones
                await delete_config_from_db(session, self.config_model, section)

                validated_section = ConfigSection.model_validate(
                    {"section": section, "values": value}
                )

                if isinstance(validated_section.values, dict):
                    for sub_key, sub_value in validated_section.values.items():
                        await _upsert_config(
                            session, self.config_model, section, sub_key, sub_value
                        )
                        history_entries.append((section, sub_key, sub_value))
                elif isinstance(validated_section.values, list):
                    await _upsert_config(
                        session,
                        self.config_model,
                        section,
                        "__list__",
                        validated_section.values,
                    )
                    history_entries.append(
                        (section, "__list__", validated_section.values)
                    )
                elif isinstance(validated_section.values, (str, int, float, bool)):
                    await _upsert_config(
                        session,
                        self.config_model,
                        section,
                        "__val__",
                        validated_section.values,
                    )
                    history_entries.append(
                        (section, "__val__", validated_section.values)
                    )
                else:
                    raise ValueError("Section value must be a dictionary or list.")

                redis_data = validated_section.values

            else:
                validated_entry = ConfigEntry.model_validate(
                    {"section": section, "key": key, "value": value}
                )
                await _upsert_config(
                    session, self.config_model, section, key, validated_entry.value
                )
                history_entries.append(
                    (
                        section,
                        key,
                        validated_entry.value.value
                        if isinstance(validated_entry.value, ConfigValue)
                        else validated_entry.value,
                    )
                )

                redis_data = (
                    validated_entry.value
                    if not isinstance(validated_entry.value, ConfigValue)
                    else validated_entry.value.value
                )

            for entry in history_entries:
                await set_config_history(session, *entry, updated_by)

            return redis_data, timestamp

        # Run the entire DB transaction in `db_operation`
        redis_data, timestamp = await db_operation(
            self.db_session_factory, db_transaction
        )

        # Publish changes to Redis
        async def redis_operations():
            message = json.dumps(
                {
                    "action": "set",
                    "section": section,
                    "key": key or "__full_section__",
                    "new_value": redis_data,
                    "timestamp": timestamp,
                    "updated_by": updated_by,
                }
            )
            async with self.redis_manager.get_client(self.redis_url) as client:
                await client.set(
                    f"{section}:{key or '__full_section__'}", json.dumps(redis_data)
                )
                await client.publish("config_changes", message)

        await retry_redis_operation(redis_operations)

        logger.info(
            f"✅ Config updated: [{section}:{key or 'entire section'}] -> {redis_data}"
        )

    async def _get_config_from_redis(
        self, client, section: str, key: Union[str, None] = None
    ) -> Union[Any, Dict[str, Any], None]:
        """
        Retrieve configuration value from Redis.

        Args:
            client: Redis client instance.
            section (str): The section name.
            key (Union[str, None]): The key name (if fetching a specific config).

        Returns:
            - If key is provided, returns the specific value.
            - If key is None, returns the entire section dictionary.
            - If key is None and `__full_section__` exists, extracts and returns its content.
        """
        cache_key = f"{section}:{key}" if key else section
        redis_value = await client.get(cache_key)

        if redis_value:
            try:
                value = json.loads(redis_value)  # Ensure JSON decoding
            except json.JSONDecodeError:
                return redis_value  # If not JSON, return raw string

            # Restore full section if stored using `__full_section__`
            if key is None and isinstance(value, dict) and "__full_section__" in value:
                return value["__full_section__"]  # Extract actual section data

            return value  # Return normally

        return None  # Return None if key not found

    async def get_config(
        self, section: str, key: Union[str, None] = None
    ) -> Union[Any, Dict[str, Any], None]:
        """
        Retrieve a configuration value from Redis or the database.

        Args:
            section (str): The section name.
            key (Union[str, None]): The specific key within the section. Defaults to None.

        Returns:
            Union[Any, Dict[str, Any], None]:
            - If key is provided, returns the value.
            - If key is None, returns a dictionary of key-value pairs in the section.
            - Returns None if the config is not found.
        """
        cache_key = f"{section}:{key}" if key else section
        logger.debug(f"Trying to get Redis client from {self.redis_url}")

        # First, check Redis
        async with self.redis_manager.get_client(self.redis_url) as client:
            redis_value = await self._get_config_from_redis(client, section, key)
            if redis_value is not None:
                return redis_value

        logger.debug(f"⚠️ Redis miss. Querying DB for {section}:{key}...")

        # If not in Redis, check DB
        async def fetch_config(session):
            return await get_config_from_db(session, self.config_model, section, key)

        db_value = await db_operation(self.db_session_factory, fetch_config)

        if db_value:
            async with self.redis_manager.get_client(self.redis_url) as client:
                await client.set(cache_key, json.dumps(db_value))

        return db_value

    async def export_config(
        self,
        section: Union[str, None] = None,
        key: Union[str, None] = None,
        fmt: str = "json",
        as_bytes: bool = False,
        raw: bool = False,
    ) -> Union[str, bytes, Dict[str, Any]]:
        """
        Export configuration as a formatted string (JSON, YAML, or TOML), or return raw data if `raw=True`.
        - If `section` is None, export all configurations.
        - If `raw=True`, return the raw dictionary instead of a formatted string.
        """

        async def fetch_configs(session):
            if section is None:
                return await get_all_configs_from_db(session, self.config_model)
            return await get_config_from_db(session, self.config_model, section, key)

        config_data = await db_operation(self.db_session_factory, fetch_configs)

        if not config_data:
            return {} if raw else (b"" if as_bytes else "")

        # Fix: Extract `.value` from ConfigValue instances before export
        def unwrap(value):
            return value.value if isinstance(value, ConfigValue) else value

        if isinstance(config_data, dict):
            config_data = {k: unwrap(v) for k, v in config_data.items()}
        else:
            config_data = unwrap(config_data)

        if raw:
            return config_data

        result = convert_config(config_data, fmt)
        return result.encode() if as_bytes else result

    async def delete_config(
        self, section: str, key: Union[str, None] = None, updated_by: str = "system"
    ) -> None:
        """Delete configuration from DB and Redis."""

        async def db_transaction(session):
            timestamp = datetime.now(tz=timezone.utc).isoformat()

            deleted = await delete_config_from_db(
                session, self.config_model, section, key
            )

            if not deleted:
                raise HTTPException(status_code=404, detail="Config not found.")

            # Log deletion in history within the same transaction
            await set_config_history(
                session, section, key or "__full_section__", None, updated_by
            )

            return timestamp

        # Run the entire DB transaction in `db_operation`
        timestamp = await db_operation(self.db_session_factory, db_transaction)

        # Delete from Redis after successful DB transaction
        async def redis_operations():
            message = json.dumps(
                {
                    "action": "delete",
                    "section": section,
                    "key": key or "__full_section__",
                    "timestamp": timestamp,
                    "updated_by": updated_by,
                }
            )
            async with self.redis_manager.get_client(self.redis_url) as client:
                if key:
                    redis_key = f"{section}:{key}"
                    await client.delete(redis_key)
                else:
                    await client.delete(f"{section}")
                    # Delete all keys within the section (wildcard pattern)
                    pattern = f"{section}:*"  # Match all keys in section
                    keys_to_delete = await client.keys(pattern)  # Fetch matching keys
                    if keys_to_delete:
                        await client.delete(*keys_to_delete)

                await client.publish("config_changes", message)

        await retry_redis_operation(redis_operations)

        logger.info(f"✅ Deleted config: [{section}:{key}]")

    async def get_config_history(
        self, section: str = None, key: str = None, limit: int = 10, offset: int = 0
    ):
        """Retrieve config history using standardized DB access."""

        async def fetch_history(session):
            return await fetch_config_history_from_db(
                session, self.config_history_model, section, key, limit, offset
            )

        # Ensure session is managed by `db_operation`
        return await db_operation(self.db_session_factory, fetch_history)

    async def listen_to_config_changes(
        self, callback: Callable[[dict], None] = None
    ) -> None:
        """
        Listen for config changes via Redis Pub/Sub and execute a callback.

        Args:
            callback (Callable[[dict], None]): Function to be triggered when a config changes.
        """
        logger.info("🔄 Listening for config changes from Redis.")
        async with self.redis_manager.get_client(self.redis_url) as client:
            pubsub = client.pubsub()
            await pubsub.subscribe("config_changes")

            async for message in pubsub.listen():
                if message is None:
                    break  # Stop listening if Redis disconnects
                if message["type"] == "message":
                    try:
                        change_data = json.loads(message["data"])  # Read event as JSON

                        action = change_data.get("action")
                        if action == "set":
                            # Single Config Update
                            section, key = change_data["section"], change_data["key"]
                            cache_key = f"{section}:{key}"

                            async with self.redis_manager.get_client(
                                self.redis_url
                            ) as redis_client:
                                new_value = await self._get_config_from_redis(
                                    redis_client, section, key
                                )
                                logger.info(
                                    f"🔄 Config updated: [{cache_key}] -> {new_value}"
                                )

                        elif action == "bulk_set":
                            # Bulk Config Update
                            updated_configs = change_data["configs"]
                            parsed_updates = {}

                            for key, value in updated_configs.items():
                                # Deserialize JSON-encoded strings
                                parsed_value = safe_json_loads(value)
                                parsed_updates[key] = parsed_value

                            logger.info(
                                f"📢 Bulk config update received: {parsed_updates}"
                            )

                        elif action == "delete":
                            # Config Deletion
                            section, key = change_data["section"], change_data["key"]
                            cache_key = f"{section}:{key}"
                            logger.info(f"🗑️ Config removed: [{cache_key}]")

                        # If a callback is provided, call it with the change data
                        if callback:
                            await callback(change_data)

                    except (ValueError, KeyError) as e:
                        logger.error(
                            f"❌ Pub/Sub message parsing error: {message['data']} | {e}"
                        )

    async def close(self):
        """Ensure all resources (DB, Redis) are closed properly."""
        if self.subscriber_task:
            self.subscriber_task.cancel()
        self.redis_manager.stop_health_checks()
        self.redis_manager.stop_cleanup()
        await self.redis_manager.close_all_pools()

    async def get_bulk_config(self, sections: List[str]) -> Dict[str, Any]:
        """
        Retrieve multiple configurations in one call.

        Args:
            sections (list[str]): List of sections to fetch.

        Returns:
            dict[str, Any]: Dictionary with section names as keys and values as config data.
        """
        result = {}
        async with self.redis_manager.get_client(self.redis_url) as client:
            redis_values = await client.mget(sections)  # Fetch multiple values at once

            for section, redis_value in zip(sections, redis_values):
                if redis_value:
                    result[section] = json.loads(redis_value)
                else:

                    async def fetch_config(session, section=section):
                        return await get_config_from_db(
                            session, self.config_model, section
                        )

                    db_value = await db_operation(self.db_session_factory, fetch_config)

                    if db_value:
                        result[section] = db_value
                        await client.set(
                            section, json.dumps(db_value)
                        )  # Cache in Redis

        return result

    async def set_bulk_config(
        self, configs: Dict[str, Any], updated_by: str = "system"
    ) -> None:
        """
        Set multiple configurations in bulk **atomically**.

        Args:
            configs (dict): Dictionary where keys are section names and values can be:
                - A dictionary of key-value pairs.
                - A list (which will be stored under "__list__").
                - Other values: str, int, float, bool
            updated_by (str): User making the update.

        Returns:
            None
        """

        async def db_transaction(session):
            timestamp = datetime.now(tz=timezone.utc).isoformat()
            history_entries = []  # Collect updates before logging history
            redis_updates = {}  # Store Redis updates for batch insert

            for section, values in configs.items():
                if isinstance(
                    values, list
                ):  # If section is a list, store under "__list__"
                    values = {"__list__": values}
                if isinstance(values, (str, int, float, bool)):
                    values = {"__val__": values}
                if not isinstance(values, dict):
                    raise ValueError(
                        f"Invalid format for section '{section}'. Expected dict or list."
                    )

                for key, value in values.items():
                    validated_entry = ConfigEntry.model_validate(
                        {"section": section, "key": key, "value": value}
                    )

                    # Set the config in the database **inside the same transaction**
                    await set_config_in_db(
                        session,
                        self.config_model,
                        section,
                        key,
                        validated_entry.value,
                        updated_by,
                    )

                    # Collect history entries for batch logging
                    history_entries.append(
                        (
                            section,
                            key,
                            validated_entry.value.value
                            if isinstance(validated_entry.value, ConfigValue)
                            else validated_entry.value,
                        )
                    )

                    # Ensure Redis stores JSON-safe values
                    redis_updates[f"{section}:{key}"] = json.dumps(
                        validated_entry.value.value
                        if isinstance(validated_entry.value, ConfigValue)
                        else validated_entry.value
                    )

            # Log all history entries **inside the same transaction**
            for entry in history_entries:
                await set_config_history(session, *entry, updated_by)

            return redis_updates, timestamp  # Return for Redis update

        # Execute all DB operations atomically
        redis_updates, timestamp = await db_operation(
            self.db_session_factory, db_transaction
        )

        # Update Redis in a single batch
        async def redis_operations():
            message = json.dumps(
                {
                    "action": "bulk_set",
                    "timestamp": timestamp,
                    "updated_by": updated_by,
                    "configs": redis_updates,  # Include all updates in the message
                }
            )
            async with self.redis_manager.get_client(self.redis_url) as client:
                if redis_updates:
                    await client.mset(redis_updates)  # Batch insert into Redis
                await client.publish("config_changes", message)

        await retry_redis_operation(redis_operations)

        logger.info(
            f"✅ Bulk config update successful: {len(redis_updates)} items updated."
        )
