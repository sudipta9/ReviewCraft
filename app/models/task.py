"""
Database Models for Code Review Tasks

This module defines the database models for tracking code review analysis tasks.
It follows SQLAlchemy 2.0 patterns with async support and proper type hints.

Features:
- Task status tracking
- Task metadata and configuration
- Relationship to analysis results
- Retry and error handling
"""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import JSON, Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.pr_analysis import PRAnalysis


class TaskStatus(str, Enum):
    """Task execution status enumeration."""

    PENDING = "pending"  # Task created but not started
    PROCESSING = "processing"  # Task is currently being executed
    COMPLETED = "completed"  # Task completed successfully
    FAILED = "failed"  # Task failed with error
    CANCELLED = "cancelled"  # Task was cancelled
    RETRY = "retry"  # Task is being retried


class TaskPriority(str, Enum):
    """Task priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class Task(Base):
    """
    Model for tracking code review analysis tasks.

    This model stores information about asynchronous code review tasks,
    including their status, configuration, and execution metadata.
    """

    __tablename__ = "tasks"

    # Task identification
    celery_task_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        unique=True,
        index=True,
        doc="Celery task ID for tracking async execution",
    )

    # Task configuration
    task_type: Mapped[str] = mapped_column(
        String(50),
        default="pr_analysis",
        doc="Type of analysis task (pr_analysis, file_analysis, etc.)",
    )

    priority: Mapped[TaskPriority] = mapped_column(
        String(20), default=TaskPriority.NORMAL, doc="Task execution priority"
    )

    # GitHub PR information
    repo_url: Mapped[str] = mapped_column(String(500), doc="GitHub repository URL")

    repo_owner: Mapped[str] = mapped_column(
        String(100), doc="Repository owner/organization name"
    )

    repo_name: Mapped[str] = mapped_column(String(100), doc="Repository name")

    pr_number: Mapped[int] = mapped_column(Integer, doc="Pull request number")

    pr_title: Mapped[Optional[str]] = mapped_column(
        String(500), doc="Pull request title"
    )

    pr_author: Mapped[Optional[str]] = mapped_column(
        String(100), doc="Pull request author username"
    )

    # Task execution status
    status: Mapped[TaskStatus] = mapped_column(
        String(20), default=TaskStatus.PENDING, index=True, doc="Current task status"
    )

    progress: Mapped[int] = mapped_column(
        Integer, default=0, doc="Task progress percentage (0-100)"
    )

    # Execution metadata
    started_at: Mapped[Optional[datetime]] = mapped_column(
        doc="Timestamp when task execution started"
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        doc="Timestamp when task execution completed"
    )

    # Error handling
    error_message: Mapped[Optional[str]] = mapped_column(
        Text, doc="Error message if task failed"
    )

    error_details: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, doc="Detailed error information (stack trace, context, etc.)"
    )

    retry_count: Mapped[int] = mapped_column(
        Integer, default=0, doc="Number of retry attempts"
    )

    max_retries: Mapped[int] = mapped_column(
        Integer, default=3, doc="Maximum number of retry attempts"
    )

    # Task configuration
    config: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, doc="Task-specific configuration and parameters"
    )

    # GitHub API metadata
    github_token_used: Mapped[bool] = mapped_column(
        Boolean, default=False, doc="Whether GitHub token was used for this task"
    )

    rate_limit_remaining: Mapped[Optional[int]] = mapped_column(
        Integer, doc="GitHub API rate limit remaining after task"
    )

    # Relationships
    pr_analysis: Mapped[Optional["PRAnalysis"]] = relationship(
        "PRAnalysis", back_populates="task", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """String representation of the task."""
        return (
            f"<Task(id='{self.id}', "
            f"repo='{self.repo_owner}/{self.repo_name}', "
            f"pr_number={self.pr_number}, "
            f"status='{self.status}')>"
        )

    @property
    def is_completed(self) -> bool:
        """Check if task is in a completed state."""
        return self.status in {
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        }

    @property
    def is_running(self) -> bool:
        """Check if task is currently running."""
        return self.status == TaskStatus.PROCESSING

    @property
    def can_retry(self) -> bool:
        """Check if task can be retried."""
        return self.status == TaskStatus.FAILED and self.retry_count < self.max_retries

    @property
    def execution_time(self) -> Optional[float]:
        """Calculate task execution time in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def update_progress(self, progress: int, message: Optional[str] = None) -> None:
        """
        Update task progress.

        Args:
            progress: Progress percentage (0-100)
            message: Optional progress message
        """
        self.progress = max(0, min(100, progress))
        if message and self.config:
            if "progress_messages" not in self.config:
                self.config["progress_messages"] = []
            self.config["progress_messages"].append(
                {
                    "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                    "progress": progress,
                    "message": message,
                }
            )

    def mark_started(self) -> None:
        """Mark task as started."""
        self.status = TaskStatus.PROCESSING
        self.started_at = datetime.now(tz=timezone.utc)
        self.progress = 0

    def mark_completed(self) -> None:
        """Mark task as completed successfully."""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now(tz=timezone.utc)
        self.progress = 100

    def mark_failed(
        self, error_message: str, error_details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Mark task as failed.

        Args:
            error_message: Human-readable error message
            error_details: Detailed error information
        """
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.now(tz=timezone.utc)
        self.error_message = error_message
        self.error_details = error_details or {}

    def increment_retry(self) -> None:
        """Increment retry count and update status."""
        self.retry_count += 1
        if self.retry_count <= self.max_retries:
            self.status = TaskStatus.RETRY
        else:
            self.status = TaskStatus.FAILED
