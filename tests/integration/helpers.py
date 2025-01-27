from unified_config.core.config_manager import ConfigManager


async def flush_redis_cache(config_manager: ConfigManager):
    """Helper function to flush Redis before or after tests."""
    async with config_manager.redis_manager.get_client(
        config_manager.redis_url
    ) as redis_client:
        print("🗑️ Manually flushing Redis after test...")
        await redis_client.flushdb()
