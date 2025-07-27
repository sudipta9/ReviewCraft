"""Models package initialization."""

# Import all models to ensure they are registered with SQLAlchemy
from .task import Task, TaskStatus, TaskPriority
from .pr_analysis import (
    PRAnalysis,
    FileAnalysis,
    Issue,
    AnalysisStatus,
    IssueType,
    IssueSeverity,
)

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
