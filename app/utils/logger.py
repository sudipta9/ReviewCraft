"""
Logging Utilities Module

This module provides a centralized logging configuration using structlog.
It supports both structured (JSON) and human-readable logging formats.

Features:
- Structured logging with JSON output
- Human-readable development logging
- Automatic log correlation with request IDs
- Performance logging decorators
- Configurable log levels and formats
"""

import asyncio
import logging
import sys
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional

import structlog
from structlog.typing import FilteringBoundLogger

from app.config import settings


def configure_logging() -> None:
    """
    Configure structlog with appropriate processors and formatting.

    This function sets up:
    - JSON formatting for production
    - Human-readable formatting for development
    - Automatic timestamping
    - Log level filtering
    - Exception formatting
    """
    # Configure standard library logging
    logging.basicConfig(
        format=settings.logging.format,
        level=getattr(logging, settings.logging.level.upper()),
        stream=sys.stdout,
    )

    # Configure structlog processors
    processors = [
        structlog.processors.TimeStamper(fmt="ISO"),
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
    ]

    if settings.logging.structured and settings.is_production:
        # Production: JSON output
        processors.extend(
            [structlog.processors.dict_tracebacks, structlog.processors.JSONRenderer()]
        )
    else:
        # Development: Human-readable output
        processors.extend(
            [
                structlog.processors.dict_tracebacks,
                structlog.dev.ConsoleRenderer(colors=True),
            ]
        )

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        context_class=dict,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> FilteringBoundLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        FilteringBoundLogger: Configured logger instance
    """
    return structlog.get_logger(name)


def log_performance(func_name: Optional[str] = None) -> Callable:
    """
    Decorator to log function performance metrics.

    Args:
        func_name: Optional custom function name for logging

    Returns:
        Callable: Decorated function

    Example:
        @log_performance()
        def expensive_function():
            # Some expensive operation
            pass
    """

    def decorator(func: Callable) -> Callable:
        logger = get_logger(__name__)
        name = func_name or f"{func.__module__}.{func.__name__}"

        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    duration = time.time() - start_time
                    logger.info(
                        "Function completed",
                        function=name,
                        duration_seconds=round(duration, 4),
                        success=True,
                    )
                    return result
                except Exception as e:
                    duration = time.time() - start_time
                    logger.error(
                        "Function failed",
                        function=name,
                        duration_seconds=round(duration, 4),
                        error=str(e),
                        error_type=type(e).__name__,
                        success=False,
                    )
                    raise

            return async_wrapper
        else:

            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    duration = time.time() - start_time
                    logger.info(
                        "Function completed",
                        function=name,
                        duration_seconds=round(duration, 4),
                        success=True,
                    )
                    return result
                except Exception as e:
                    duration = time.time() - start_time
                    logger.error(
                        "Function failed",
                        function=name,
                        duration_seconds=round(duration, 4),
                        error=str(e),
                        error_type=type(e).__name__,
                        success=False,
                    )
                    raise

            return sync_wrapper

    return decorator


def log_api_request(
    request_id: str,
    method: str,
    path: str,
    user_id: Optional[str] = None,
    additional_context: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log API request details.

    Args:
        request_id: Unique request identifier
        method: HTTP method
        path: Request path
        user_id: Optional user identifier
        additional_context: Additional context to log
    """
    logger = get_logger("api")
    context = {
        "request_id": request_id,
        "method": method,
        "path": path,
        "user_id": user_id,
    }

    if additional_context:
        context.update(additional_context)

    logger.info("API request received", **context)


def log_api_response(
    request_id: str,
    status_code: int,
    duration_ms: float,
    response_size: Optional[int] = None,
) -> None:
    """
    Log API response details.

    Args:
        request_id: Unique request identifier
        status_code: HTTP status code
        duration_ms: Request duration in milliseconds
        response_size: Optional response size in bytes
    """
    logger = get_logger("api")
    logger.info(
        "API response sent",
        request_id=request_id,
        status_code=status_code,
        duration_ms=round(duration_ms, 2),
        response_size=response_size,
        success=200 <= status_code < 400,
    )


def log_task_start(task_id: str, task_name: str, **context) -> None:
    """
    Log Celery task start.

    Args:
        task_id: Task identifier
        task_name: Task name
        **context: Additional context
    """
    logger = get_logger("celery")
    logger.info("Task started", task_id=task_id, task_name=task_name, **context)


def log_task_success(
    task_id: str, task_name: str, duration_seconds: float, **context
) -> None:
    """
    Log Celery task success.

    Args:
        task_id: Task identifier
        task_name: Task name
        duration_seconds: Task duration
        **context: Additional context
    """
    logger = get_logger("celery")
    logger.info(
        "Task completed successfully",
        task_id=task_id,
        task_name=task_name,
        duration_seconds=round(duration_seconds, 4),
        success=True,
        **context,
    )


def log_task_failure(
    task_id: str, task_name: str, error: Exception, duration_seconds: float, **context
) -> None:
    """
    Log Celery task failure.

    Args:
        task_id: Task identifier
        task_name: Task name
        error: Exception that caused the failure
        duration_seconds: Task duration before failure
        **context: Additional context
    """
    logger = get_logger("celery")
    logger.error(
        "Task failed",
        task_id=task_id,
        task_name=task_name,
        error=str(error),
        error_type=type(error).__name__,
        duration_seconds=round(duration_seconds, 4),
        success=False,
        **context,
    )


def log_github_api_call(
    endpoint: str,
    method: str,
    status_code: int,
    rate_limit_remaining: Optional[int] = None,
    rate_limit_reset: Optional[int] = None,
) -> None:
    """
    Log GitHub API call details.

    Args:
        endpoint: GitHub API endpoint
        method: HTTP method
        status_code: Response status code
        rate_limit_remaining: Remaining rate limit
        rate_limit_reset: Rate limit reset timestamp
    """
    logger = get_logger("github")
    logger.info(
        "GitHub API call",
        endpoint=endpoint,
        method=method,
        status_code=status_code,
        rate_limit_remaining=rate_limit_remaining,
        rate_limit_reset=rate_limit_reset,
        success=200 <= status_code < 400,
    )


def log_ai_request(
    model: str,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    total_tokens: Optional[int] = None,
    duration_seconds: Optional[float] = None,
) -> None:
    """
    Log AI/LLM request details.

    Args:
        model: AI model used
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens
        total_tokens: Total tokens used
        duration_seconds: Request duration
    """
    logger = get_logger("ai")
    logger.info(
        "AI request completed",
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        duration_seconds=round(duration_seconds, 4) if duration_seconds else None,
    )


class LoggerMixin:
    """
    Mixin class to add logging capabilities to any class.

    Usage:
        class MyService(LoggerMixin):
            def do_something(self):
                self.logger.info("Doing something")
    """

    @property
    def logger(self) -> FilteringBoundLogger:
        """Get logger instance for this class."""
        if not hasattr(self, "_logger"):
            self._logger = get_logger(
                f"{self.__class__.__module__}.{self.__class__.__name__}"
            )
        return self._logger


# Initialize logging on module import
configure_logging()
