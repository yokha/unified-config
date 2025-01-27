import asyncio
import json
import logging
from typing import Any, Dict, Literal, Optional, Union

from fastapi import (APIRouter, Depends, HTTPException, Query, Response,
                     WebSocket, WebSocketDisconnect)
from sqlalchemy.ext.asyncio import AsyncSession
from unified_config.core.config_manager import ConfigManager
from unified_config.core.db_access import safe_json_loads
from unified_config.core.schemas import ConfigEntry, ConfigSection

from config_manager import get_config_manager
from models.function import FunctionModel
from schemas.schemas import FunctionCreate, FunctionResponse
from services.config_service import ConfigService
from services.function_service import (add_function, delete_function_by_name,
                                       get_all_functions)
from src.core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


# Config API Endpoints
@router.post("/config/set")
async def set_config(
    payload: Union[ConfigEntry, ConfigSection],  # Accept both types
    manager: ConfigManager = Depends(get_config_manager),
):
    """
    Set a configuration value (single entry) or an entire section.
    - If `key` is provided, updates a specific key (`ConfigEntry`).
    - If `key` is missing, updates an entire section (`ConfigSection`).
    """

    if isinstance(payload, ConfigEntry):
        # Single key-value pair
        return await ConfigService.set_config(
            manager=manager,
            section=payload.section,
            key=payload.key,
            value=payload.value.value,
        )

    elif isinstance(payload, ConfigSection):
        # Entire section update
        return await ConfigService.set_config(
            manager=manager,
            section=payload.section,
            key=None,
            value=payload.values,
        )

    raise HTTPException(status_code=400, detail="Invalid request format")


@router.get("/config/get")
async def get_config(
    section: str, key: str = None, manager: ConfigManager = Depends(get_config_manager)
):
    """Get a configuration value"""
    config_value = await ConfigService.get_config(manager, section, key)
    if config_value is None:
        raise HTTPException(status_code=404, detail="Configuration not found")

    return config_value


@router.delete("/config/delete")
async def delete_config(
    section: str,
    key: Union[str, None] = None,
    manager: ConfigManager = Depends(get_config_manager),
):
    """Delete a configuration value"""
    return await ConfigService.delete_config(manager, section, key)


@router.get("/config/export")
async def export_config(
    format: str = "json", manager: ConfigManager = Depends(get_config_manager)
):
    """Export all stored configurations"""
    # Normalize input (support "yml" as "yaml")
    format = format.lower()
    if format == "yml":
        format = "yaml"

    # Validate format manually
    if format not in {"json", "yaml", "toml"}:
        raise HTTPException(
            status_code=400,
            detail="Unsupported format. Choose 'json', 'yaml', or 'toml'.",
        )

    all_config = await ConfigService.export_all_configs(manager, format)

    if all_config is None:
        raise HTTPException(status_code=404, detail="Empty DB Configuration")

    # Properly return JSON
    if format == "json":
        return json.loads(all_config)

    # Return YAML/TOML as text
    return Response(content=all_config, media_type="text/plain")


@router.get("/config/history")
async def get_config_history(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    section: str = None,
    key: str = None,
    manager=Depends(get_config_manager),
):
    """Retrieve paginated config history via FunctionService"""
    return await ConfigService.get_config_history(manager, section, key, limit, offset)


@router.put("/config/update_bulk")
async def update_bulk_config(
    configs: Dict[str, Any],
    manager: ConfigManager = Depends(get_config_manager),
):
    """
    Bulk update configuration settings.

    Request Body Example (JSON):
    {
        "app_settings": {
            "theme": "dark",
            "language": "en"
        },
        "database": {
            "host": "localhost",
            "port": 5432
        }
    }
    """
    if not configs:
        raise HTTPException(status_code=400, detail="Empty configuration payload.")

    transformed_config = {}

    for section, value in configs.items():
        if isinstance(value, list):
            # Store lists under "__list__" key
            transformed_config[section] = {"__list__": value}
        elif isinstance(value, (str, int, float, bool)):
            # Store primitive values under "__section__" key
            transformed_config[section] = {"__val__": value}
        else:
            transformed_config[section] = value  # Keep dicts unchanged

    try:
        await manager.set_bulk_config(configs=transformed_config, updated_by="api_user")
        return {"message": "Configurations updated successfully!"}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to update configs: {str(e)}"
        )


@router.get("/function/", response_model=list[FunctionResponse])
async def list_functions(
    db: AsyncSession = Depends(get_db),
    config_manager: ConfigManager = Depends(
        get_config_manager
    ),  # Inject ConfigManager
):
    """Retrieve all stored functions using the service layer, respecting config."""
    return await get_all_functions(db, config_manager)


@router.post("/function/", response_model=FunctionResponse)
async def create_function(
    function_data: FunctionCreate,
    db: AsyncSession = Depends(get_db),
    config_manager: ConfigManager = Depends(
        get_config_manager
    ),  # Inject ConfigManager
):
    """Create a new function using the service layer, respecting config."""
    return await add_function(db, config_manager, function_data)


@router.delete("/function/{name}")
async def delete_function(
    name: str,
    db: AsyncSession = Depends(get_db),
    config_manager: ConfigManager = Depends(
        get_config_manager
    ),  # Inject ConfigManager
):
    """Delete a function using the service layer, respecting config."""
    return await delete_function_by_name(db, config_manager, name)


@router.websocket("/config/updates")
async def websocket_config_updates(
    websocket: WebSocket, manager: ConfigManager = Depends(get_config_manager)
):
    """WebSocket endpoint to stream real-time config changes via Redis Pub/Sub."""
    await websocket.accept()
    logger.info("📡 WebSocket client connected for live config updates.")

    try:
        async with manager.redis_manager.get_client(manager.redis_url) as client:
            pubsub = client.pubsub()
            await pubsub.subscribe("config_changes")

            last_known_config = {}  # Local cache for filtering unchanged values

            while True:
                try:
                    message = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True), timeout=30.0
                    )
                    if message:
                        change_data = json.loads(message["data"])  # Read event as JSON

                        if "configs" in change_data:
                            filtered_changes = {}

                            for key, new_value in change_data["configs"].items():
                                new_value = safe_json_loads(new_value)  # Ensure correct type
                                old_value = last_known_config.get(key)

                                if old_value != new_value:  # 🔥 Only send changed values
                                    filtered_changes[key] = new_value
                                    last_known_config[key] = new_value  # Update cache

                            if filtered_changes:  # 🔥 Only send if there are actual changes
                                update_payload = {"configs": filtered_changes}
                                await websocket.send_json(update_payload)
                                logger.info(f"📡 WebSocket sent update: {update_payload}")

                except asyncio.TimeoutError:
                    logger.info("⌛ WebSocket connection idle, sending ping...")
                    await websocket.send_json({"ping": "keepalive"})

                except (ValueError, KeyError) as e:
                    logger.error(f"❌ Pub/Sub message parsing error: {message['data']} | {e}")

    except Exception as e:
        logger.error(f"❌ WebSocket connection error: {e}")
    finally:
        logger.info("🔌 WebSocket client disconnected.")
