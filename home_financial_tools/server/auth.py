import secrets
from typing import Dict, Optional

import bcrypt
from fastapi import HTTPException, Request, status


class AuthenticationError(HTTPException):
    """Custom exception for authentication failures."""

    def __init__(self):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid authentication credentials")


def load_users(config: dict) -> Dict[str, str]:
    """
    Load users from config and hash their passwords with bcrypt.

    Args:
        config: Configuration dictionary containing 'allowed_users'

    Returns:
        Dictionary mapping username to bcrypt password hash
    """
    allowed_users = config.get("allowed_users", {})
    hashed_users = {}

    for username, password in allowed_users.items():
        # Hash the password with bcrypt
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        hashed_users[username] = password_hash

    return hashed_users


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
