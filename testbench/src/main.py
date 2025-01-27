import asyncio
import logging
import os
import subprocess

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.endpoints import router as api_router
from core.database import close_db, init_db
from task import start_background_tasks

# Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Add CORS Middleware to allow frontend (Angular) requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],  # Only allow requests from Angular app
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, PUT, DELETE)
    allow_headers=["*"],  # Allow all headers
)

# Include API Endpoints
app.include_router(api_router)


async def run_migrations():
    """Run Alembic migrations automatically on startup."""
    logger.info("⚙️ Running database migrations...")
    venv_bin = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", ".venv", "bin", "alembic"
    )
    try:
        subprocess.run([venv_bin, "upgrade", "head"], check=True)
        logger.info("✅ Migrations applied successfully!")
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Failed to apply migrations: {e}")
        raise e


@app.on_event("startup")
async def startup_event():
    """Initialize DB and apply migrations on startup."""
    logger.info("🚀 Starting application...")
    await run_migrations()  # Apply migrations on startup
    await init_db()  # Initialize database
    # logger.info("🔄 Running background tasks in Gunicorn master process...")
    start_background_tasks()  # Only runs in master process


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup and close database connection on shutdown."""
    logger.info("🛑 Shutting down...")
    await close_db()


if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=8080, reload=True)
