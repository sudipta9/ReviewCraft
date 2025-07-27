"""
Database Models for Pull Request Analysis Results

This module defines the database models for storing pull request analysis results,
including file-level analysis, detected issues, and analysis metadata.

Features:
- Comprehensive PR analysis storage
- File-level analysis tracking
- Issue detection and categorization
- Analysis metrics and metadata
"""

from asyncio import Task
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any

from sqlalchemy import String, Text, Integer, Float, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AnalysisStatus(str, Enum):
    """Analysis execution status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class IssueType(str, Enum):
    """Code issue type classification."""

    STYLE = "style"  # Code style and formatting issues
    BUG = "bug"  # Potential bugs or errors
    PERFORMANCE = "performance"  # Performance improvements
    SECURITY = "security"  # Security vulnerabilities
    BEST_PRACTICE = "best_practice"  # Best practice violations
    COMPLEXITY = "complexity"  # Code complexity issues
    MAINTAINABILITY = "maintainability"  # Maintainability concerns
    DOCUMENTATION = "documentation"  # Documentation issues


class IssueSeverity(str, Enum):
    """Issue severity levels."""

    INFO = "info"  # Informational only
    LOW = "low"  # Minor issue
    MEDIUM = "medium"  # Moderate issue
    HIGH = "high"  # Important issue
    CRITICAL = "critical"  # Critical issue requiring immediate attention


class PRAnalysis(Base):
    """
    Model for storing pull request analysis results.

    This model contains the overall analysis results for a GitHub pull request,
    including summary statistics and relationships to detailed file analyses.
    """

    __tablename__ = "pr_analyses"

    # Task relationship
    task_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        index=True,
        doc="Reference to the analysis task",
    )

    # PR metadata
    pr_url: Mapped[str] = mapped_column(
        String(500), doc="Full URL to the GitHub pull request"
    )

    base_branch: Mapped[str] = mapped_column(
        String(200), doc="Base branch name (target branch)"
    )

    head_branch: Mapped[str] = mapped_column(
        String(200), doc="Head branch name (source branch)"
    )

    base_sha: Mapped[str] = mapped_column(String(40), doc="Base commit SHA")

    head_sha: Mapped[str] = mapped_column(String(40), doc="Head commit SHA")

    # Analysis status and timing
    status: Mapped[AnalysisStatus] = mapped_column(
        String(20), default=AnalysisStatus.PENDING, doc="Current analysis status"
    )

    analysis_started_at: Mapped[Optional[datetime]] = mapped_column(
        doc="When analysis started"
    )

    analysis_completed_at: Mapped[Optional[datetime]] = mapped_column(
        doc="When analysis completed"
    )

    # Analysis summary statistics
    total_files_analyzed: Mapped[int] = mapped_column(
        Integer, default=0, doc="Total number of files analyzed"
    )

    total_lines_analyzed: Mapped[int] = mapped_column(
        Integer, default=0, doc="Total number of lines analyzed"
    )

    total_issues_found: Mapped[int] = mapped_column(
        Integer, default=0, doc="Total number of issues found"
    )

    critical_issues: Mapped[int] = mapped_column(
        Integer, default=0, doc="Number of critical issues"
    )

    high_issues: Mapped[int] = mapped_column(
        Integer, default=0, doc="Number of high severity issues"
    )

    medium_issues: Mapped[int] = mapped_column(
        Integer, default=0, doc="Number of medium severity issues"
    )

    low_issues: Mapped[int] = mapped_column(
        Integer, default=0, doc="Number of low severity issues"
    )

    info_issues: Mapped[int] = mapped_column(
        Integer, default=0, doc="Number of informational issues"
    )

    # Analysis quality score (0-100)
    quality_score: Mapped[Optional[float]] = mapped_column(
        Float, doc="Overall code quality score (0-100)"
    )

    maintainability_score: Mapped[Optional[float]] = mapped_column(
        Float, doc="Code maintainability score (0-100)"
    )

    complexity_score: Mapped[Optional[float]] = mapped_column(
        Float, doc="Code complexity score (0-100)"
    )

    # AI analysis metadata
    ai_model_used: Mapped[Optional[str]] = mapped_column(
        String(100), doc="AI model used for analysis"
    )

    ai_tokens_consumed: Mapped[Optional[int]] = mapped_column(
        Integer, doc="Total AI tokens consumed"
    )

    ai_analysis_duration: Mapped[Optional[float]] = mapped_column(
        Float, doc="Time spent on AI analysis (seconds)"
    )

    # Analysis configuration
    analysis_config: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, doc="Configuration used for this analysis"
    )

    # Analysis summary
    summary: Mapped[Optional[str]] = mapped_column(
        Text, doc="Human-readable analysis summary"
    )

    recommendations: Mapped[Optional[List[str]]] = mapped_column(
        JSON, doc="List of improvement recommendations"
    )

    # Error information
    error_message: Mapped[Optional[str]] = mapped_column(
        Text, doc="Error message if analysis failed"
    )

    # Relationships
    task: Mapped["Task"] = relationship("Task", back_populates="pr_analysis")

    file_analyses: Mapped[List["FileAnalysis"]] = relationship(
        "FileAnalysis", back_populates="pr_analysis", cascade="all, delete-orphan"
    )

    issues: Mapped[List["Issue"]] = relationship(
        "Issue", back_populates="pr_analysis", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """String representation of the PR analysis."""
        return (
            f"<PRAnalysis(id='{self.id}', "
            f"task_id='{self.task_id}', "
            f"status='{self.status}', "
            f"total_issues={self.total_issues_found})>"
        )

    @property
    def analysis_duration(self) -> Optional[float]:
        """Calculate total analysis duration in seconds."""
        if self.analysis_started_at and self.analysis_completed_at:
            return (
                self.analysis_completed_at - self.analysis_started_at
            ).total_seconds()
        return None

    @property
    def is_completed(self) -> bool:
        """Check if analysis is completed."""
        return self.status in {AnalysisStatus.COMPLETED, AnalysisStatus.FAILED}

    @property
    def has_critical_issues(self) -> bool:
        """Check if analysis found critical issues."""
        return self.critical_issues > 0

    def update_statistics(self) -> None:
        """Update analysis statistics from related file analyses and issues."""
        # This will be called after all file analyses are complete
        if self.file_analyses:
            self.total_files_analyzed = len(self.file_analyses)
            self.total_lines_analyzed = sum(
                fa.lines_analyzed or 0 for fa in self.file_analyses
            )

        if self.issues:
            self.total_issues_found = len(self.issues)
            self.critical_issues = len(
                [i for i in self.issues if i.severity == IssueSeverity.CRITICAL]
            )
            self.high_issues = len(
                [i for i in self.issues if i.severity == IssueSeverity.HIGH]
            )
            self.medium_issues = len(
                [i for i in self.issues if i.severity == IssueSeverity.MEDIUM]
            )
            self.low_issues = len(
                [i for i in self.issues if i.severity == IssueSeverity.LOW]
            )
            self.info_issues = len(
                [i for i in self.issues if i.severity == IssueSeverity.INFO]
            )


class FileAnalysis(Base):
    """
    Model for storing individual file analysis results.

    This model contains analysis results for individual files within a PR,
    including metrics, issues, and AI-generated insights.
    """

    __tablename__ = "file_analyses"

    # PR analysis relationship
    pr_analysis_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("pr_analyses.id", ondelete="CASCADE"),
        index=True,
        doc="Reference to the PR analysis",
    )

    # File information
    file_path: Mapped[str] = mapped_column(
        String(1000), doc="Relative path to the file in the repository"
    )

    file_name: Mapped[str] = mapped_column(String(255), doc="File name")

    file_extension: Mapped[Optional[str]] = mapped_column(
        String(10), doc="File extension"
    )

    file_type: Mapped[Optional[str]] = mapped_column(
        String(50), doc="Programming language or file type"
    )

    # File metrics
    lines_total: Mapped[Optional[int]] = mapped_column(
        Integer, doc="Total lines in the file"
    )

    lines_analyzed: Mapped[Optional[int]] = mapped_column(
        Integer, doc="Number of lines analyzed"
    )

    lines_added: Mapped[Optional[int]] = mapped_column(
        Integer, doc="Number of lines added in this PR"
    )

    lines_removed: Mapped[Optional[int]] = mapped_column(
        Integer, doc="Number of lines removed in this PR"
    )

    # Analysis status
    analysis_status: Mapped[AnalysisStatus] = mapped_column(
        String(20), default=AnalysisStatus.PENDING, doc="Status of file analysis"
    )

    # Quality metrics
    complexity_score: Mapped[Optional[float]] = mapped_column(
        Float, doc="File complexity score"
    )

    maintainability_index: Mapped[Optional[float]] = mapped_column(
        Float, doc="Maintainability index score"
    )

    test_coverage: Mapped[Optional[float]] = mapped_column(
        Float, doc="Test coverage percentage"
    )

    # Issue counts for this file
    issues_count: Mapped[int] = mapped_column(
        Integer, default=0, doc="Total issues found in this file"
    )

    critical_issues_count: Mapped[int] = mapped_column(
        Integer, default=0, doc="Critical issues in this file"
    )

    # AI analysis
    ai_summary: Mapped[Optional[str]] = mapped_column(
        Text, doc="AI-generated summary of file changes"
    )

    ai_recommendations: Mapped[Optional[List[str]]] = mapped_column(
        JSON, doc="AI-generated recommendations for this file"
    )

    # File content diff
    diff_content: Mapped[Optional[str]] = mapped_column(
        Text, doc="Git diff content for this file"
    )

    # Analysis metadata
    analysis_tools_used: Mapped[Optional[List[str]]] = mapped_column(
        JSON, doc="List of analysis tools used on this file"
    )

    # Relationships
    pr_analysis: Mapped["PRAnalysis"] = relationship(
        "PRAnalysis", back_populates="file_analyses"
    )

    issues: Mapped[List["Issue"]] = relationship(
        "Issue", back_populates="file_analysis", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """String representation of the file analysis."""
        return (
            f"<FileAnalysis(id='{self.id}', "
            f"file_path='{self.file_path}', "
            f"issues_count={self.issues_count})>"
        )


class Issue(Base):
    """
    Model for storing individual code issues found during analysis.

    This model represents specific issues detected in code, including
    their location, type, severity, and suggested fixes.
    """

    __tablename__ = "issues"

    # Relationships
    pr_analysis_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("pr_analyses.id", ondelete="CASCADE"),
        index=True,
        doc="Reference to the PR analysis",
    )

    file_analysis_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("file_analyses.id", ondelete="CASCADE"),
        index=True,
        doc="Reference to the file analysis (if file-specific)",
    )

    # Issue classification
    issue_type: Mapped[IssueType] = mapped_column(
        String(30), index=True, doc="Type of issue"
    )

    severity: Mapped[IssueSeverity] = mapped_column(
        String(20), index=True, doc="Issue severity level"
    )

    # Issue location
    file_path: Mapped[Optional[str]] = mapped_column(
        String(1000), doc="File path where issue was found"
    )

    line_number: Mapped[Optional[int]] = mapped_column(
        Integer, doc="Line number where issue occurs"
    )

    column_number: Mapped[Optional[int]] = mapped_column(
        Integer, doc="Column number where issue occurs"
    )

    # Issue details
    title: Mapped[str] = mapped_column(String(200), doc="Short issue title")

    description: Mapped[str] = mapped_column(Text, doc="Detailed issue description")

    code_snippet: Mapped[Optional[str]] = mapped_column(
        Text, doc="Code snippet showing the issue"
    )

    # Suggestions and fixes
    suggestion: Mapped[Optional[str]] = mapped_column(
        Text, doc="Suggested fix or improvement"
    )

    suggested_code: Mapped[Optional[str]] = mapped_column(
        Text, doc="Suggested code replacement"
    )

    # Analysis metadata
    rule_id: Mapped[Optional[str]] = mapped_column(
        String(100), doc="ID of the rule that detected this issue"
    )

    tool_name: Mapped[Optional[str]] = mapped_column(
        String(50), doc="Name of the tool that detected this issue"
    )

    confidence: Mapped[Optional[float]] = mapped_column(
        Float, doc="Confidence score of the detection (0-1)"
    )

    # Additional context
    tags: Mapped[Optional[List[str]]] = mapped_column(
        JSON, doc="Additional tags for categorization"
    )

    references: Mapped[Optional[List[str]]] = mapped_column(
        JSON, doc="Links to documentation or references"
    )

    # Relationships
    pr_analysis: Mapped["PRAnalysis"] = relationship(
        "PRAnalysis", back_populates="issues"
    )

    file_analysis: Mapped[Optional["FileAnalysis"]] = relationship(
        "FileAnalysis", back_populates="issues"
    )

    def __repr__(self) -> str:
        """String representation of the issue."""
        return (
            f"<Issue(id='{self.id}', "
            f"type='{self.issue_type}', "
            f"severity='{self.severity}', "
            f"file='{self.file_path}', "
            f"line={self.line_number})>"
        )

    @property
    def is_critical(self) -> bool:
        """Check if this is a critical issue."""
        return self.severity == IssueSeverity.CRITICAL

    @property
    def location_string(self) -> str:
        """Get a human-readable location string."""
        parts = []
        if self.file_path:
            parts.append(self.file_path)
        if self.line_number:
            parts.append(f"line {self.line_number}")
            if self.column_number:
                parts.append(f"column {self.column_number}")
        return ":".join(parts) if parts else "unknown location"
