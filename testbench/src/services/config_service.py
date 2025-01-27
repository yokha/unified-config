import logging
from typing import Literal, Union

from fastapi import HTTPException
from unified_config.core.config_manager import ConfigManager

# Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConfigService:
    @staticmethod
    async def set_config(manager: ConfigManager, section: str, key: str, value: str):
        """Insert or update a configuration using ConfigManager"""
        try:
            await manager.set_config(section, key, value)
            return {"message": "Configuration saved"}
        except ValueError as ve:
            logger.error(f"❌ Bad request. Error {ve}")
            raise HTTPException(status_code=400, detail=f"Bad Request. Error: {ve}")
        except Exception as e:
            logger.error(f"❌ Error setting config. Error {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @staticmethod
    async def get_config(manager: ConfigManager, section: str, key: str):
        """Fetch a config value using ConfigManager"""
        value = await manager.get_config(section, key)
        return value

    @staticmethod
    async def delete_config(
        manager: ConfigManager, section: str, key: Union[str, None] = None
    ):
        """Delete a configuration value using ConfigManager"""
        await manager.delete_config(section, key)
        return {"status": "deleted"}

    @staticmethod
    async def export_all_configs(
        manager: ConfigManager, format: Literal["json", "yaml", "toml"] = "json"
    ):
        """Return all configurations in the requested format using ConfigManager"""

        try:
            return await manager.export_config(fmt=format)

        except Exception as e:
            logger.error(f"❌ Error exporting configs in format {format}: {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

    @staticmethod
    async def get_config_history(
        manager: ConfigManager,
        section: str = None,
        key: str = None,
        limit: int = 10,
        offset: int = 0,
    ):
        """Fetch configuration history using ConfigManager"""
        return await manager.get_config_history(section, key, limit, offset)
