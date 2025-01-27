import os
from datetime import datetime, timezone
import uuid
import logging
import json
from typing import Any, Union, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, func, select
from sqlalchemy.orm import DeclarativeMeta

from unified_config.core.schemas import (
    ConfigEntry,
    ConfigSection,
    ConfigValue,
    ConfigHistory,
)


from unified_config.models.db_model import ConfigHistoryModel

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def safe_json_loads(value):
    """Attempt to parse JSON, fallback to raw value if parsing fails."""
    if isinstance(value, (dict, list)):  # Already a valid Python object, return as-is
        return value
    if not isinstance(value, str):  # Ensure only strings go to json.loads
        return value
    try:
        return json.loads(value)  # Attempt JSON parsing
    except json.JSONDecodeError:
        logger.warning(f"⚠️ Invalid JSON detected, returning raw string: {value}")
        return value  # Return raw string if JSON parsing fails


async def get_config_from_db(
    session: AsyncSession,
    model: DeclarativeMeta,
    section: Union[str, None] = None,
    key: Union[str, None] = None,
) -> Union[Any, Dict[str, Any], List[Dict[str, Any]], None]:
    """
    Retrieve configuration(s) from the database and return JSON-like structures.

    - If both `section` and `key` are provided, retrieves a single key-value pair.
    - If only `section` is provided, returns the entire section as a dictionary.
    - If no arguments are provided, returns all stored configurations as a list of dicts.

    Returns:
        - Single value if `section` and `key` are provided.
        - A dictionary `{key: value}` if only `section` is provided.
        - A list (if stored with `"__list__"`)
        - None if no data is found.
    """
    if model is None:
        return None

    query = select(model)
    if section:
        query = query.filter(model.section == section)
    if key:
        query = query.filter(model.key == key)

    result = await session.execute(query)
    configs = result.scalars().all()  # ORM objects list

    if not configs:
        return None

    if section and key:
        return safe_json_loads(configs[0].value)  # Single value

    if section:
        section_data = {config.key: safe_json_loads(config.value) for config in configs}
        if "__list__" in section_data:
            return section_data["__list__"]  # Convert `__list__` back to a list
        if "__val" in section_data:
            return section_data["__val__"]
        return section_data  # Return dictionary of key-value pairs

    # Return list of dictionaries for full DB export
    return [
        {
            "section": config.section,
            "key": config.key,
            "value": safe_json_loads(config.value),
        }
        for config in configs
    ]


async def get_all_configs_from_db(
    session: AsyncSession, model: DeclarativeMeta
) -> Dict[str, Dict[str, Any]]:
    """
    Retrieve all configurations from the database using ORM.
    Returns a dictionary structured as {section: {key: value}, ...}.
    """
    if model is None:
        return {}

    query = select(model)
    result = await session.execute(query)
    configs = result.scalars().all()

    if not configs:
        return {}

    config_data = {}
    for config in configs:
        section = config.section
        key = config.key
        value = safe_json_loads(config.value)  # Reuse existing function

        if section not in config_data:
            config_data[section] = {}

        config_data[section][key] = value

    # Convert `__list__` to a proper list representation
    for section, data in config_data.items():
        if "__list__" in data:
            config_data[section] = data["__list__"]  # Convert to list
        if "__val__" in data:
            config_data[section] = data["__val__"]

    return config_data


async def set_config_in_db(
    session: AsyncSession,
    model: DeclarativeMeta,
    section: str,
    key: Union[str, None] = None,
    value: Any = None,
    updated_by="system",
) -> None:
    """
    Add or update a configuration in the database. Supports:

    - A single key-value pair.
    - A full section as a dictionary (nested key-value pairs).
    - A full section as a list.

    Args:
        session (AsyncSession): The SQLAlchemy async database session.
        model (DeclarativeMeta): The database model.
        section (str): The section name.
        key (Union[str, None]): The key within the section.
        value (Any): The value to store.

    Raises:
        ValueError: If key is None but value is neither a dictionary nor a list.
    """
    if key is None:
        # Ensure section is either a dictionary or a list
        validated_section = ConfigSection.model_validate(
            {"section": section, "values": value}
        )

        # DELETE existing keys for this section before inserting new values
        await delete_config_from_db(session, model, section)

        if isinstance(validated_section.values, dict):
            for sub_key, sub_value in validated_section.values.items():
                validated_entry = ConfigEntry.model_validate(
                    {"section": section, "key": sub_key, "value": sub_value}
                )
                await _upsert_config(
                    session,
                    model,
                    validated_entry.section,
                    validated_entry.key,
                    validated_entry.value,
                )
        elif isinstance(validated_section.values, list):
            validated_entry = ConfigEntry.model_validate(
                {
                    "section": section,
                    "key": "__list__",
                    "value": validated_section.values,
                }
            )
            await _upsert_config(
                session,
                model,
                validated_entry.section,
                validated_entry.key,
                validated_entry.value,
            )
        else:
            validated_entry = ConfigEntry.model_validate(
                {
                    "section": section,
                    "key": "__val__",
                    "value": validated_section.values,
                }
            )
            await _upsert_config(
                session,
                model,
                validated_entry.section,
                validated_entry.key,
                validated_entry.value,
            )
    else:
        # Validate the individual key-value entry
        validated_entry = ConfigEntry.model_validate(
            {"section": section, "key": key, "value": value}
        )
        await _upsert_config(
            session,
            model,
            validated_entry.section,
            validated_entry.key,
            validated_entry.value,
        )

    logger.info(
        f"✅ Config set for section='{section}', key='{key or 'entire section'}'."
    )


async def _upsert_config(
    session: AsyncSession,
    model: DeclarativeMeta,
    section: str,
    key: str,
    value: Any,
) -> None:
    """
    Inserts or updates a configuration key-value pair in the database.

    Args:
        session (AsyncSession): SQLAlchemy async database session.
        model (DeclarativeMeta): Database model.
        section (str): The configuration section.
        key (str): The configuration key.
        value (Any): The configuration value.
    """
    # Ensure value is JSON serializable
    if isinstance(value, ConfigValue):
        value = value.value  # Extract the raw value from ConfigValue

    json_value = json.dumps(value)  # Serialize value to JSON

    obj = model(section=section, key=key, value=json_value)

    await session.merge(obj)

    logger.debug(f"✅ Upserted config: section={section}, key={key}, value={value}")


async def delete_config_from_db(
    session: AsyncSession,
    model: DeclarativeMeta,
    section: str,
    key: Union[str, None] = None,
) -> None:
    """
    Delete configuration(s) from the database.

    Args:
        session (AsyncSession): The SQLAlchemy async database session.
        model (DeclarativeMeta): The database model.
        section (str): The configuration section to delete.
        key (Union[str, None]): The specific key within the section.

    Return: True if resource deleted, otherwise False
    """
    query = delete(model).filter(model.section == section)
    if key:
        query = query.filter(model.key == key)

    result = await session.execute(query)

    deleted_count = result.rowcount  # Check number of rows affected
    if deleted_count:
        logger.info(
            f"Deleted config for section='{section}', key='{key or 'entire section'}'."
        )
        return True
    logger.info(
        f"No config found for section='{section}', key='{key or 'entire section'}'."
    )
    return False


async def fetch_config_history_from_db(
    session: AsyncSession,
    model: DeclarativeMeta,
    section: Union[str, None] = None,
    key: Union[str, None] = None,
    limit: int = 10,
    offset: int = 0,
) -> Dict[str, Any]:
    """Retrieve paginated configuration history and total count from the database"""
    total_query = select(func.count()).select_from(  # pylint: disable=not-callable
        model
    )

    if section is not None:
        total_query = total_query.where(model.section == section)

    if key is not None:
        total_query = total_query.where(model.key == key)

    total_result = await session.execute(total_query)
    total_count = total_result.scalar() or 0  # Ensure it's always an integer

    # Fetch paginated data (Apply same section & key filter)
    query = select(model).order_by(model.timestamp.desc()).limit(limit).offset(offset)

    if section is not None:
        query = query.where(model.section == section)

    if key is not None:
        query = query.where(model.key == key)

    result = await session.execute(query)
    history = result.scalars().all()

    return {
        "total_count": total_count,  # Correct total count
        "data": [
            {
                "section": h.section,
                "key": h.key,
                # Deserialize `new_value` if it's stored as a JSON string
                "new_value": safe_json_loads(h.new_value)
                if isinstance(h.new_value, str)
                else h.new_value,
                "timestamp": h.timestamp,
            }
            for h in history
        ],
    }


async def set_config_history(
    session: AsyncSession, section: str, key: str, new_value: Any, updated_by: str
):
    """Save a configuration change into the configuration history table."""
    logger.info(f"Inserting history for {section}:{key} in worker {os.getpid()}")
    # Ensure consistency: Convert only strings to JSON
    if isinstance(new_value, str):
        new_value = json.dumps(new_value)  # Convert strings properly
    elif not isinstance(new_value, (dict, list, int, float, bool, type(None))):
        raise ValueError(f"Unsupported data type for history: {type(new_value)}")

    # Create a new history record using the Pydantic model
    history_entry = ConfigHistory(
        id=str(uuid.uuid4()),  # Generate a unique UUID
        section=section,
        key=key,
        new_value=new_value,
        timestamp=datetime.now(tz=timezone.utc).replace(
            tzinfo=None
        ),  # Convert to naive datetime
        updated_by=updated_by,
    )

    # Convert Pydantic model to ORM model
    history_orm = ConfigHistoryModel(**history_entry.model_dump())

    # Add entry to the session and commit
    session.add(history_orm)

    return history_entry  # Returning it for reference/debugging
