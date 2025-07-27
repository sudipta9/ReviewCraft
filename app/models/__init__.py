"""Models package initialization."""

# Import all models to ensure they are registered with SQLAlchemy
from .pr_analysis import (
    AnalysisStatus,
    FileAnalysis,
    Issue,
    IssueSeverity,
    IssueType,
    PRAnalysis,
)
from .task import Task, TaskPriority, TaskStatus

# Make models available at package level
__all__ = [
    # Task models
    "Task",
    "TaskStatus",
    "TaskPriority",
    # PR Analysis models
    "PRAnalysis",
    "FileAnalysis",
    "Issue",
    # Enums
    "AnalysisStatus",
    "IssueType",
    "IssueSeverity",
]
