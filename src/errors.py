from typing import Any, Dict, Union

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from src.config import logger


# Custom exceptions
class AppException(Exception):
    """Base exception for application-specific errors."""

    def __init__(self, status_code: int, detail: Union[str, Dict[str, Any]]):
        self.status_code = status_code
        self.detail = detail


class DatabaseException(AppException):
    """Exception for database-related errors."""

    def __init__(self, detail: str = "Database error occurred"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail
        )


class AuthenticationException(AppException):
    """Exception for authentication-related errors."""

    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


class AuthorizationException(AppException):
    """Exception for authorization-related errors."""

    def __init__(self, detail: str = "Not authorized to perform this action"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class ResourceNotFoundException(AppException):
    """Exception for resource not found errors."""

    def __init__(self, detail: str = "Resource not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class ValidationException(AppException):
    """Exception for validation errors."""

    def __init__(self, detail: Union[str, Dict[str, Any]] = "Validation error"):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail
        )


class BadRequestException(AppException):
    """Exception for bad request errors."""

    def __init__(self, detail: Union[str, Dict[str, Any]] = "Bad request"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


# Exception handlers
async def app_exception_handler(request: Request, exc: AppException):
    """Handler for application-specific exceptions."""
    logger.error(f"Application error: {exc.detail} (Status: {exc.status_code})")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    formatted_errors = [
        {
            "type": error["type"],
            "loc": error["loc"],
            "msg": error["msg"],
            "input": error["input"],
        }
        for error in exc.errors()
    ]

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": formatted_errors},
    )


async def pydantic_validation_exception_handler(request: Request, exc: ValidationError):
    """Handler for Pydantic validation errors."""
    errors = exc.errors()
    logger.error(f"Pydantic validation error: {errors}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": errors},
    )


async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    """Handler for SQLAlchemy errors."""
    logger.error(f"Database error: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Database error occurred. Please try again later."},
    )


async def general_exception_handler(request: Request, exc: Exception):
    """Handler for all other exceptions."""
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred. Please try again later."},
    )


# Function to register exception handlers with FastAPI app
def register_exception_handlers(app):
    """Register all exception handlers with the FastAPI application."""
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(ValidationError, pydantic_validation_exception_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)

    logger.info("Exception handlers registered")
