"""Configuration schema validation using Pydantic."""

from typing import Dict

from pydantic import BaseModel, Field, field_validator


class DatabaseConfig(BaseModel):
    """Database configuration."""

    path: str = Field(..., description="Path to SQLite database file")


class ServerConfig(BaseModel):
    """Server configuration."""

    host: str = Field(default="0.0.0.0", description="Server host address")
    port: int = Field(default=8000, ge=1, le=65535, description="Server port number")


class Config(BaseModel):
    """Main configuration schema."""

    database: DatabaseConfig
    server: ServerConfig = Field(default_factory=ServerConfig)
    allowed_users: Dict[str, str] = Field(
        default_factory=dict, description="Map of username to password for authentication"
    )

    @field_validator("allowed_users")
    @classmethod
    def validate_users(cls, v: Dict[str, str]) -> Dict[str, str]:
        """Validate that allowed_users is not empty."""
        if not v:
            raise ValueError("At least one user must be configured in allowed_users")
        return v
