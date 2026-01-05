import logging
import secrets
from typing import Dict, Optional

import bcrypt
from fastapi import HTTPException, Request, status

logger = logging.getLogger(__name__)


class AuthenticationError(HTTPException):
    """Custom exception for authentication failures."""

    def __init__(self):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid authentication credentials")


def load_users_from_db(db, config: dict) -> Dict[str, bytes]:
    """
    Load users from database, syncing with config file.

    On first run, users from config are hashed and stored in database.
    On subsequent runs, users are loaded from database (no rehashing).
    If new users are added to config, they are added to database.

    To change a password: Delete the user from the database, then restart
    the server. The user will be re-added from config with the new password.

    Args:
        db: Database instance
        config: Configuration dictionary containing 'allowed_users'

    Returns:
        Dictionary mapping username to bcrypt password hash from database
    """
    config_users = config.get("allowed_users", {})
    logger.info(f"Found {len(config_users)} users in config: {list(config_users.keys())}")

    # Get existing users from database
    db_users = db.get_all_users()
    logger.info(f"Found {len(db_users)} users in database: {list(db_users.keys())}")

    # Sync: Add any config users that aren't in database
    for username, password in config_users.items():
        if username not in db_users:
            logger.info(f"New user '{username}' found in config, hashing and storing in database")
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            db.save_user(username, password_hash)
            db_users[username] = password_hash
        else:
            logger.debug(f"User '{username}' already exists in database, using stored hash")

    # Return all users from database
    logger.info(f"Successfully loaded {len(db_users)} users from database")
    return db_users


def verify_password(password: str, password_hash: bytes) -> bool:
    """
    Verify a password against a bcrypt hash.

    Args:
        password: Plain text password to verify
        password_hash: Bcrypt hash to verify against

    Returns:
        True if password matches, False otherwise
    """
    return bcrypt.checkpw(password.encode('utf-8'), password_hash)


def generate_session_token() -> str:
    """
    Generate a random session token.

    Returns:
        Random hex string of 32 bytes (64 characters)
    """
    return secrets.token_hex(32)


def get_current_user(request: Request) -> str:
    """
    FastAPI dependency to validate authentication token and get current user.

    Args:
        request: FastAPI request object

    Returns:
        Username of authenticated user

    Raises:
        AuthenticationError: If token is missing or invalid
    """
    # Get token from header
    token = request.headers.get("X-Auth-Token")

    if not token:
        raise AuthenticationError()

    # Validate token against database sessions
    db = request.app.state.db
    username = db.get_session(token)

    if not username:
        raise AuthenticationError()

    return username
