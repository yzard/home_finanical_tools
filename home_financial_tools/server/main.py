import os

import uvicorn
import yaml
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
 

from home_financial_tools.server.db import Database
from home_financial_tools.server.router import router


def create_application(config_path: str) -> FastAPI:
    """Application factory for the Invoice Web Service."""
    with open(config_path, "r") as f:
        config_dict = yaml.safe_load(f)
    
    # Validate config with Pydantic
    from home_financial_tools.server.config import Config
    try:
        config = Config(**config_dict)
    except Exception as e:
        raise ValueError(f"Invalid configuration: {e}") from e

    db_path: str = config.database.path
    # Ensure directory exists for sqlite
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    app = FastAPI(title="Invoice Web Service")

    # Shared resources
    app.state.config = config
    app.state.db = Database(db_path)
    
    # Authentication setup
    from home_financial_tools.server.auth import load_users
    app.state.allowed_users = load_users(config.model_dump())
    app.state.sessions = {}  # {token: username}
    
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Register router
    app.include_router(router)

    # Static files for web UI
    app.mount("/", StaticFiles(directory="home_financial_tools/webgui", html=True), name="static")

    return app


def main() -> None:
    """Main entrypoint for the server."""
    config_path = os.environ.get("CONFIG_PATH", "sample/config.yaml")

    # Load and validate config for server settings
    with open(config_path, "r") as f:
        config_dict = yaml.safe_load(f)
    
    from home_financial_tools.server.config import Config
    try:
        config = Config(**config_dict)
    except Exception as e:
        raise ValueError(f"Invalid configuration: {e}") from e

    host = os.environ.get("HOST", config.server.host)
    port = int(os.environ.get("PORT", config.server.port))

    app = create_application(config_path)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
