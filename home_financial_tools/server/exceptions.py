import logging
import traceback
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppException(Exception):
    """Base exception for application errors."""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppException):
    """Resource not found."""

    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status_code=404)


class AuthenticationError(AppException):
    """Authentication failed."""

    def __init__(self, message: str = "Authentication required"):
        super().__init__(message, status_code=401)


def _format_request_info(request: Request, body: Any = None) -> str:
    """Format request information for logging."""
    info = [
        f"Method: {request.method}",
        f"URL: {request.url}",
        f"Client: {request.client.host if request.client else 'unknown'}",
    ]
    if body:
        info.append(f"Body: {body}")
    return "\n".join(info)


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all unhandled exceptions."""
    # Try to get request body for logging
    body = None
    try:
        body = await request.json()
    except Exception:
        pass

    # Log full details
    logger.error(
        f"Unhandled exception:\n"
        f"{_format_request_info(request, body)}\n"
        f"Exception: {exc}\n"
        f"Traceback:\n{traceback.format_exc()}"
    )

    return JSONResponse(status_code=500, content={"detail": f"Internal server error: {str(exc)}"})


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handle application-specific exceptions."""
    logger.warning(f"App exception: {exc.message} (status={exc.status_code})")
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


def setup_exception_handlers(app: FastAPI) -> None:
    """Register exception handlers on the app."""
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)
