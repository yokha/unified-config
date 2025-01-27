import asyncio
import json
import logging
import os
from uuid import uuid4

from fastapi import FastAPI

from config_manager import get_config_manager
from database import SessionLocal  # Assuming async SQLAlchemy session
from models.config import ConfigHistoryModel  # Assuming the history model

# Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def listen_for_config_changes():
    """Subscribe to Redis Pub/Sub and store config updates in the database"""
    async for manager in get_config_manager():
        logger.info(f"====> Just for test {os.getpid()}")
        # async with manager.redis_manager.get_client(manager.redis_url) as client:
        #     pubsub = client.pubsub()
        #     await pubsub.subscribe("config_changes")  # Listen for changes

        #     logger.debug("✅ Listening for config changes...")
        #     async for message in pubsub.listen():
        #         if message["type"] == "message":
        #             try:
        #                 data = json.loads(message["data"])
        #                 logger.debug(f"🔄 Config updated: {data}")  # Log change

        #                 # new_value = data.get("new_value", None)  # Default to None for deletions

        #                 # # Store in DB
        #                 # async with SessionLocal() as session:
        #                 # # async with async_session() as session:
        #                 #     history_entry = ConfigHistoryModel(
        #                 #         id=str(uuid4()),
        #                 #         section=data["section"],
        #                 #         key=data.get("key"),  # Can be None for full section updates
        #                 #         new_value=new_value,
        #                 #         updated_by=data["updated_by"],
        #                 #     )
        #                 #     session.add(history_entry)
        #                 #     await session.commit()

        #             except json.JSONDecodeError:
        #                 logger.error(f"⚠️ Failed to parse config update: {message['data']}")


def start_background_tasks():
    """Hook for FastAPI lifespan"""
    loop = asyncio.get_event_loop()
    loop.create_task(listen_for_config_changes())  # Start config change listener
