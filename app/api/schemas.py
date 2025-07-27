"""
API Schemas Module

This module defines Pydantic models for API request/response validation and serialization.
Following OpenAPI 3.0 standards for comprehensive API documentation.

Features:
- Request/Response validation
- Automatic OpenAPI schema generation
- Type safety and documentation
- Error response standardization
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum

from pydantic import BaseModel, Field

from app.models import (
    TaskStatus,
    TaskPriority,
    AnalysisStatus,
    IssueType,
    IssueSeverity,
)


class HealthStatus(str, Enum):
    """Health check status values."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"


# Base response models
class BaseResponse(BaseModel):
    """Base response model with common fields."""

    success: bool = Field(description="Whether the request was successful")
    message: str = Field(description="Human-readable message")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Response timestamp"
    )

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class ErrorDetail(BaseModel):
    """Detailed error information."""

    code: str = Field(description="Error code")
    message: str = Field(description="Error message")
    field: Optional[str] = Field(
        default=None, description="Field that caused the error"
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional error context"
    )


class ErrorResponse(BaseResponse):
    """Standardized error response."""

    success: bool = Field(default=False, description="Always false for errors")
    message: str = Field(default="An error occurred", description="Error message")
    error: ErrorDetail = Field(description="Error details")


# Health check schemas
class HealthCheckResponse(BaseResponse):
    """Health check response."""

    status: HealthStatus = Field(description="Overall health status")
    checks: Dict[str, Dict[str, Any]] = Field(description="Individual service checks")
    uptime: float = Field(description="Application uptime in seconds")
    version: str = Field(description="Application version")


# PR Analysis request/response schemas
class PRAnalysisRequest(BaseModel):
    """Request model for PR analysis."""

    repo_url: str = Field(description="GitHub repository URL")
    pr_number: int = Field(description="Pull request number", gt=0)
    github_token: Optional[str] = Field(
        None, description="GitHub personal access token"
    )
    priority: TaskPriority = Field(
        default=TaskPriority.NORMAL, description="Analysis priority level"
    )
    analysis_options: Optional[Dict[str, Any]] = Field(
        None, description="Custom analysis configuration options"
    )


class PRAnalysisResponse(BaseResponse):
    """Response model for PR analysis submission."""

    task_id: str = Field(description="Unique task identifier")
    status: TaskStatus = Field(description="Current task status")
    estimated_completion: Optional[datetime] = Field(
        None, description="Estimated completion time"
    )
    priority: TaskPriority = Field(description="Task priority")


# Task status schemas
class TaskStatusResponse(BaseResponse):
    """Response model for task status check."""

    task_id: str = Field(description="Task identifier")
    status: TaskStatus = Field(description="Current task status")
    progress: Optional[int] = Field(
        None, description="Progress percentage (0-100)", ge=0, le=100
    )
    created_at: datetime = Field(description="Task creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    estimated_completion: Optional[datetime] = Field(
        None, description="Estimated completion time"
    )
    error_message: Optional[str] = Field(
        None, description="Error message if task failed"
    )


# Analysis results schemas
class IssueSchema(BaseModel):
    """Individual code issue schema."""

    id: str = Field(description="Issue identifier")
    type: IssueType = Field(description="Issue type")
    severity: IssueSeverity = Field(description="Issue severity")
    line_number: Optional[int] = Field(
        None, description="Line number where issue occurs"
    )
    column_number: Optional[int] = Field(
        None, description="Column number where issue occurs"
    )
    description: str = Field(description="Issue description")
    suggestion: Optional[str] = Field(None, description="Suggested fix")
    rule_id: Optional[str] = Field(
        None, description="Analysis rule that detected this issue"
    )
    confidence: Optional[float] = Field(
        None, description="Confidence score (0.0-1.0)", ge=0.0, le=1.0
    )


class FileAnalysisSchema(BaseModel):
    """File analysis result schema."""

    id: str = Field(description="File analysis identifier")
    file_path: str = Field(description="Relative path to the file")
    language: Optional[str] = Field(None, description="Detected programming language")
    lines_added: int = Field(description="Number of lines added")
    lines_removed: int = Field(description="Number of lines removed")
    complexity_score: Optional[float] = Field(
        None, description="Code complexity score", ge=0.0
    )
    issues: List[IssueSchema] = Field(description="Issues found in this file")


class AnalysisSummary(BaseModel):
    """Analysis summary statistics."""

    total_files: int = Field(description="Total number of files analyzed")
    total_lines_added: int = Field(description="Total lines added across all files")
    total_lines_removed: int = Field(description="Total lines removed across all files")
    total_issues: int = Field(description="Total number of issues found")
    critical_issues: int = Field(description="Number of critical issues")
    high_issues: int = Field(description="Number of high severity issues")
    medium_issues: int = Field(description="Number of medium severity issues")
    low_issues: int = Field(description="Number of low severity issues")
    languages_detected: List[str] = Field(description="Programming languages detected")
    overall_score: Optional[float] = Field(
        None, description="Overall code quality score (0.0-10.0)", ge=0.0, le=10.0
    )


class PRAnalysisResultsResponse(BaseResponse):
    """Response model for analysis results."""

    task_id: str = Field(description="Task identifier")
    status: AnalysisStatus = Field(description="Analysis status")
    github_repo: str = Field(description="GitHub repository")
    pr_number: int = Field(description="Pull request number")
    analysis_started_at: datetime = Field(description="Analysis start time")
    analysis_completed_at: Optional[datetime] = Field(
        None, description="Analysis completion time"
    )
    summary: AnalysisSummary = Field(description="Analysis summary")
    files: List[FileAnalysisSchema] = Field(description="Per-file analysis results")
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional analysis metadata"
    )


# List responses with pagination
class PaginationInfo(BaseModel):
    """Pagination information."""

    page: int = Field(description="Current page number", ge=1)
    per_page: int = Field(description="Items per page", ge=1, le=100)
    total_items: int = Field(description="Total number of items", ge=0)
    total_pages: int = Field(description="Total number of pages", ge=0)
    has_next: bool = Field(description="Whether there are more pages")
    has_prev: bool = Field(description="Whether there are previous pages")


class TaskListResponse(BaseResponse):
    """Response model for task list."""

    tasks: List[TaskStatusResponse] = Field(description="List of tasks")
    pagination: PaginationInfo = Field(description="Pagination information")


# Analysis configuration schemas
class AnalysisConfig(BaseModel):
    """Analysis configuration options."""

    include_style_issues: bool = Field(
        default=True, description="Include code style issues"
    )
    include_security_issues: bool = Field(
        default=True, description="Include security issues"
    )
    include_performance_issues: bool = Field(
        default=True, description="Include performance issues"
    )
    include_best_practices: bool = Field(
        default=True, description="Include best practice violations"
    )
    max_issues_per_file: int = Field(
        default=50, description="Maximum issues to report per file", ge=1, le=200
    )
    severity_threshold: IssueSeverity = Field(
        default=IssueSeverity.LOW, description="Minimum severity level to include"
    )
    custom_rules: Optional[List[str]] = Field(
        None, description="Custom analysis rules to apply"
    )


# Webhook schemas (for future GitHub integration)
class WebhookPayload(BaseModel):
    """GitHub webhook payload for automatic PR analysis."""

    action: str = Field(description="Webhook action")
    pull_request: Dict[str, Any] = Field(description="Pull request data")
    repository: Dict[str, Any] = Field(description="Repository data")
    sender: Dict[str, Any] = Field(description="Event sender data")


# Export all schemas
__all__ = [
    # Base models
    "BaseResponse",
    "ErrorDetail",
    "ErrorResponse",
    # Health check
    "HealthStatus",
    "HealthCheckResponse",
    # PR Analysis
    "PRAnalysisRequest",
    "PRAnalysisResponse",
    "TaskStatusResponse",
    "PRAnalysisResultsResponse",
    # Analysis components
    "IssueSchema",
    "FileAnalysisSchema",
    "AnalysisSummary",
    # Lists and pagination
    "PaginationInfo",
    "TaskListResponse",
    # Configuration
    "AnalysisConfig",
    # Webhooks
    "WebhookPayload",
]
