import argparse
import logging
import os
from pathlib import Path

import uvicorn
import yaml
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from home_financial_tools.server.auth import load_users_from_db
from home_financial_tools.server.config import Config
from home_financial_tools.server.db import Database
from home_financial_tools.server.exceptions import setup_exception_handlers
from home_financial_tools.server.router import router

logger = logging.getLogger(__name__)


def create_application(config_path: str) -> FastAPI:
    """Application factory for the Invoice Web Service."""
    with open(config_path, "r") as f:
        config_dict = yaml.safe_load(f)

    try:
        config = Config(**config_dict)
    except Exception as e:
        raise ValueError(f"Invalid configuration: {e}") from e

    # Resolve database path relative to config file directory
    config_dir = os.path.dirname(os.path.abspath(config_path))
    db_path: str = config.database.path
    if not os.path.isabs(db_path):
        db_path = os.path.join(config_dir, db_path)

    # Ensure directory exists for sqlite
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    app = FastAPI(title="Invoice Web Service")

    # Shared resources
    app.state.config = config
    app.state.db = Database(db_path)

    # Authentication setup - load users from database, syncing with config
    app.state.allowed_users = load_users_from_db(app.state.db, config.model_dump())

    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Setup global exception handler
    setup_exception_handlers(app)

    # Register router
    app.include_router(router)

    # Static files for web UI - use absolute path
    webgui_path = Path(__file__).parent.parent / "webgui"
    app.mount("/", StaticFiles(directory=str(webgui_path), html=True), name="static")

    logger.info("Application created successfully")
    return app


def main() -> None:
    """Main entrypoint for the server."""
    # Configure logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    parser = argparse.ArgumentParser(description="Invoice Web Service")
    parser.add_argument(
        "--config",
        "-c",
        default=os.environ.get("CONFIG_PATH", "sample/config.yaml"),
        help="Path to configuration file",
    )
    parser.add_argument("--host", "-H", default=None, help="Host to bind to (overrides config)")
    parser.add_argument("--port", "-p", type=int, default=None, help="Port to bind to (overrides config)")
    args = parser.parse_args()

    logger.info(f"Loading config from {args.config}")

    # Load and validate config for server settings
    with open(args.config, "r") as f:
        config_dict = yaml.safe_load(f)

    try:
        config = Config(**config_dict)
    except Exception as e:
        raise ValueError(f"Invalid configuration: {e}") from e

    host = args.host if args.host else config.server.host
    port = args.port if args.port else config.server.port

    app = create_application(args.config)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
