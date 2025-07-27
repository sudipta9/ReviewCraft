"""
Exception Utilities Module

This module provides custom exceptions and error handling utilities for the application.
It follows best practices for exception handling and provides structured error information.

Features:
- Custom exception hierarchy
- HTTP status code mapping
- Error context preservation
- Structured error responses
"""

from enum import Enum
from typing import Any, Dict, Optional


class ErrorCode(str, Enum):
    """Application-specific error codes."""

    # General errors
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    RATE_LIMITED = "RATE_LIMITED"

    # GitHub-related errors
    GITHUB_API_ERROR = "GITHUB_API_ERROR"
    GITHUB_RATE_LIMITED = "GITHUB_RATE_LIMITED"
    GITHUB_UNAUTHORIZED = "GITHUB_UNAUTHORIZED"
    GITHUB_REPO_NOT_FOUND = "GITHUB_REPO_NOT_FOUND"
    GITHUB_PR_NOT_FOUND = "GITHUB_PR_NOT_FOUND"

    # AI-related errors
    AI_SERVICE_ERROR = "AI_SERVICE_ERROR"
    AI_RATE_LIMITED = "AI_RATE_LIMITED"
    AI_INVALID_RESPONSE = "AI_INVALID_RESPONSE"
    AI_MODEL_NOT_AVAILABLE = "AI_MODEL_NOT_AVAILABLE"

    # Task-related errors
    TASK_NOT_FOUND = "TASK_NOT_FOUND"
    TASK_FAILED = "TASK_FAILED"
    TASK_TIMEOUT = "TASK_TIMEOUT"

    # Database errors
    DATABASE_ERROR = "DATABASE_ERROR"
    DATABASE_CONNECTION_ERROR = "DATABASE_CONNECTION_ERROR"

    # Code analysis errors
    CODE_ANALYSIS_FAILED = "CODE_ANALYSIS_FAILED"
    UNSUPPORTED_FILE_TYPE = "UNSUPPORTED_FILE_TYPE"
    DIFF_PARSING_ERROR = "DIFF_PARSING_ERROR"


class BaseApplicationError(Exception):
    """Base exception class for all application errors."""

    def __init__(
        self,
        message: str,
        error_code: ErrorCode,
        status_code: int = 500,
        context: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize base application error.

        Args:
            message: Human-readable error message
            error_code: Application-specific error code
            status_code: HTTP status code
            context: Additional error context
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.context = context or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary format."""
        return {
            "error": {
                "code": self.error_code.value,
                "message": self.message,
                "context": self.context,
            }
        }


class ValidationError(BaseApplicationError):
    """Raised when input validation fails."""

    def __init__(self, message: str, field: Optional[str] = None, value: Any = None):
        context = {}
        if field:
            context["field"] = field
        if value is not None:
            context["value"] = str(value)

        super().__init__(
            message=message,
            error_code=ErrorCode.VALIDATION_ERROR,
            status_code=400,
            context=context,
        )


class NotFoundError(BaseApplicationError):
    """Raised when a resource is not found."""

    def __init__(self, resource_type: str, identifier: str):
        super().__init__(
            message=f"{resource_type} not found: {identifier}",
            error_code=ErrorCode.NOT_FOUND,
            status_code=404,
            context={"resource_type": resource_type, "identifier": identifier},
        )


class UnauthorizedError(BaseApplicationError):
    """Raised when authentication is required but not provided."""

    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            message=message, error_code=ErrorCode.UNAUTHORIZED, status_code=401
        )


class ForbiddenError(BaseApplicationError):
    """Raised when access is forbidden."""

    def __init__(self, message: str = "Access forbidden"):
        super().__init__(
            message=message, error_code=ErrorCode.FORBIDDEN, status_code=403
        )


class RateLimitError(BaseApplicationError):
    """Raised when rate limit is exceeded."""

    def __init__(self, retry_after: Optional[int] = None):
        context = {}
        if retry_after:
            context["retry_after"] = retry_after

        super().__init__(
            message="Rate limit exceeded",
            error_code=ErrorCode.RATE_LIMITED,
            status_code=429,
            context=context,
        )


class GitHubAPIError(BaseApplicationError):
    """Raised when GitHub API call fails."""

    def __init__(
        self, message: str, status_code: int = 500, response_data: Optional[Dict] = None
    ):
        error_code = ErrorCode.GITHUB_API_ERROR

        if status_code == 401:
            error_code = ErrorCode.GITHUB_UNAUTHORIZED
        elif status_code == 403:
            error_code = ErrorCode.GITHUB_RATE_LIMITED
        elif status_code == 404:
            error_code = ErrorCode.GITHUB_REPO_NOT_FOUND

        context = {"github_status_code": status_code}
        if response_data:
            context["github_response"] = response_data

        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status_code if 400 <= status_code < 600 else 500,
            context=context,
        )


class GitHubPRNotFoundError(GitHubAPIError):
    """Raised when a GitHub PR is not found."""

    def __init__(self, repo: str, pr_number: int):
        super().__init__(
            message=f"Pull request #{pr_number} not found in repository {repo}",
            status_code=404,
        )
        self.error_code = ErrorCode.GITHUB_PR_NOT_FOUND
        self.context.update({"repo": repo, "pr_number": pr_number})


class AIServiceError(BaseApplicationError):
    """Raised when AI service call fails."""

    def __init__(
        self, message: str, model: Optional[str] = None, provider: Optional[str] = None
    ):
        context = {}
        if model:
            context["model"] = model
        if provider:
            context["provider"] = provider

        super().__init__(
            message=message,
            error_code=ErrorCode.AI_SERVICE_ERROR,
            status_code=500,
            context=context,
        )


class AIRateLimitError(AIServiceError):
    """Raised when AI service rate limit is exceeded."""

    def __init__(self, model: str, retry_after: Optional[int] = None):
        context = {"model": model}
        if retry_after:
            context["retry_after"] = retry_after

        super().__init__(
            message=f"AI service rate limit exceeded for model {model}", model=model
        )
        self.error_code = ErrorCode.AI_RATE_LIMITED
        self.status_code = 429


class TaskNotFoundError(BaseApplicationError):
    """Raised when a task is not found."""

    def __init__(self, task_id: str):
        super().__init__(
            message=f"Task not found: {task_id}",
            error_code=ErrorCode.TASK_NOT_FOUND,
            status_code=404,
            context={"task_id": task_id},
        )


class TaskFailedError(BaseApplicationError):
    """Raised when a task fails."""

    def __init__(self, task_id: str, reason: str):
        super().__init__(
            message=f"Task failed: {reason}",
            error_code=ErrorCode.TASK_FAILED,
            status_code=500,
            context={"task_id": task_id, "reason": reason},
        )


class DatabaseError(BaseApplicationError):
    """Raised when database operation fails."""

    def __init__(self, message: str, operation: Optional[str] = None):
        context = {}
        if operation:
            context["operation"] = operation

        super().__init__(
            message=message,
            error_code=ErrorCode.DATABASE_ERROR,
            status_code=500,
            context=context,
        )


class CodeAnalysisError(BaseApplicationError):
    """Raised when code analysis fails."""

    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        analysis_type: Optional[str] = None,
    ):
        context = {}
        if file_path:
            context["file_path"] = file_path
        if analysis_type:
            context["analysis_type"] = analysis_type

        super().__init__(
            message=message,
            error_code=ErrorCode.CODE_ANALYSIS_FAILED,
            status_code=500,
            context=context,
        )


class UnsupportedFileTypeError(CodeAnalysisError):
    """Raised when trying to analyze an unsupported file type."""

    def __init__(self, file_path: str, file_extension: str):
        super().__init__(
            message=f"Unsupported file type: {file_extension}", file_path=file_path
        )
        self.error_code = ErrorCode.UNSUPPORTED_FILE_TYPE
        self.context["file_extension"] = file_extension


def handle_exception(exc: Exception) -> BaseApplicationError:
    """
    Convert any exception to a BaseApplicationError.

    Args:
        exc: Exception to convert

    Returns:
        BaseApplicationError: Converted exception
    """
    if isinstance(exc, BaseApplicationError):
        return exc

    # Map common exceptions
    if isinstance(exc, ValueError):
        return ValidationError(str(exc))
    elif isinstance(exc, FileNotFoundError):
        return NotFoundError("File", str(exc))
    elif isinstance(exc, PermissionError):
        return ForbiddenError(str(exc))
    else:
        # Generic internal server error
        return BaseApplicationError(
            message="An unexpected error occurred",
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
            status_code=500,
            context={"original_error": str(exc), "error_type": type(exc).__name__},
        )
