"""
PR Analysis API Endpoints

This module provides the REST API endpoints for submitting and managing
pull request analysis tasks.

Endpoints:
- POST /analyze-pr: Submit a PR for analysis
- GET /status/{task_id}: Check analysis status
- GET /results/{task_id}: Get analysis results
"""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.schemas import (
    PRAnalysisRequest,
    PRAnalysisResponse,
    PRAnalysisResultsResponse,
    TaskStatusResponse,
)
from app.database import get_db_session
from app.models import AnalysisStatus, PRAnalysis, Task, TaskStatus
from app.utils import (
    NotFoundError,
    TaskNotFoundError,
    ValidationError,
    get_logger,
    log_performance,
)
from app.worker.celery_app import celery_app

logger = get_logger(__name__)

router = APIRouter()


@router.post(
    "/analyze-pr",
    response_model=PRAnalysisResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit PR for Analysis",
    description="""
    Submit a GitHub pull request for autonomous code review analysis.

    The analysis will be performed asynchronously using Celery workers.
    Use the returned task_id to check the status and retrieve results.

    **Requirements:**
    - Valid GitHub repository URL
    - Valid pull request number
    - Optional GitHub token for private repositories
    """,
)
@log_performance("analyze_pr_endpoint")
async def analyze_pr(
    request: PRAnalysisRequest, db: AsyncSession = Depends(get_db_session)
) -> PRAnalysisResponse:
    """
    Submit a pull request for analysis.

    Args:
        request: PR analysis request containing repo URL, PR number, and optional token
        db: Database session

    Returns:
        AnalyzeRequestResponse: Task ID and status information

    Raises:
        ValidationError: If request parameters are invalid
        GitHubPRNotFoundError: If the PR doesn't exist or is inaccessible
    """
    logger.info(
        "PR analysis request received",
        repo_url=request.repo_url,
        pr_number=request.pr_number,
        has_token=bool(request.github_token),
    )

    # Validate repository URL format
    if not _is_valid_github_url(request.repo_url):
        raise ValidationError(
            "Invalid GitHub repository URL format",
            field="repo_url",
            value=request.repo_url,
        )

    # Extract repository owner and name from URL
    try:
        repo_owner, repo_name = _extract_repo_info(request.repo_url)
    except ValueError as e:
        raise ValidationError(str(e), field="repo_url", value=request.repo_url)

    # Validate PR number
    if request.pr_number <= 0:
        raise ValidationError(
            "PR number must be positive", field="pr_number", value=request.pr_number
        )

    # Create task record
    task = Task(
        id=str(uuid4()),
        repo_url=request.repo_url,
        repo_owner=repo_owner,
        repo_name=repo_name,
        pr_number=request.pr_number,
        status=TaskStatus.PENDING,
        priority=request.priority,
        config={
            "repo_url": request.repo_url,
            "github_token": request.github_token,
            "requested_at": datetime.now(tz=timezone.utc).isoformat(),
            "client_info": {
                "user_agent": getattr(request, "user_agent", None),
                "ip_address": getattr(request, "client_ip", None),
            },
        },
    )

    # Save task to database
    db.add(task)
    await db.commit()
    await db.refresh(task)

    logger.info(
        "Task created successfully",
        task_id=task.id,
        repo_owner=task.repo_owner,
        repo_name=task.repo_name,
        pr_number=task.pr_number,
    )

    # Submit task to Celery
    try:
        celery_task = celery_app.send_task(
            "app.worker.celery_worker.pr_analysis_task",
            args=[
                task.id,
                request.repo_url,
                request.pr_number,
                request.github_token,
            ],
        )

        # Update task with Celery task ID
        task.celery_task_id = celery_task.id
        task.status = TaskStatus.PENDING
        await db.commit()

        logger.info(
            "Task submitted to Celery", task_id=task.id, celery_task_id=celery_task.id
        )

    except Exception as e:
        # Mark task as failed if Celery submission fails
        task.status = TaskStatus.FAILED
        task.error_message = f"Failed to submit task: {str(e)}"
        await db.commit()

        logger.error("Failed to submit task to Celery", task_id=task.id, error=str(e))
        raise

    return PRAnalysisResponse(
        success=True,
        message="PR analysis task submitted successfully",
        task_id=task.id,
        status=task.status,
        priority=task.priority,
        estimated_completion=None,  # Will be calculated during processing
    )


@router.get(
    "/status/{task_id}",
    response_model=TaskStatusResponse,
    summary="Check Task Status",
    description="""
    Check the current status of a PR analysis task.

    **Possible statuses:**
    - `pending`: Task created but not yet started
    - `queued`: Task queued for processing
    - `processing`: Task is currently being analyzed
    - `completed`: Analysis completed successfully
    - `failed`: Analysis failed with error
    """,
)
@log_performance("task_status_endpoint")
async def get_task_status(
    task_id: str, db: AsyncSession = Depends(get_db_session)
) -> TaskStatusResponse:
    """
    Get the current status of an analysis task.

    Args:
        task_id: Unique task identifier
        db: Database session

    Returns:
        TaskStatusResponse: Current task status and metadata

    Raises:
        TaskNotFoundError: If task doesn't exist
    """
    logger.debug("Task status request", task_id=task_id)

    # Fetch task from database
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise TaskNotFoundError(task_id)

    # Get Celery task status if available
    celery_progress = None

    if task.celery_task_id:
        try:
            celery_task = celery_app.AsyncResult(task.celery_task_id)

            # Get progress information if available
            if celery_task.info and isinstance(celery_task.info, dict):
                celery_progress = celery_task.info.get("progress")
        except Exception as e:
            logger.warning(
                "Failed to get Celery task status",
                task_id=task_id,
                celery_task_id=task.celery_task_id,
                error=str(e),
            )

    return TaskStatusResponse(
        success=True,
        message=f"Task status: {task.status}",
        task_id=task.id,
        status=task.status,
        progress=celery_progress,
        created_at=task.created_at,
        updated_at=task.updated_at,
        estimated_completion=None,  # Can be calculated if needed
        error_message=task.error_message,
    )


@router.get(
    "/results/{task_id}",
    response_model=PRAnalysisResultsResponse,
    summary="Get Analysis Results",
    description="""
    Retrieve the complete analysis results for a completed task.

    **Note:** This endpoint only returns data for completed tasks.
    Use the status endpoint to check if analysis is complete.
    """,
)
@log_performance("task_results_endpoint")
async def get_analysis_results(
    task_id: str, db: AsyncSession = Depends(get_db_session)
) -> PRAnalysisResultsResponse:
    """
    Get the complete analysis results for a task.

    Args:
        task_id: Unique task identifier
        db: Database session

    Returns:
        PRAnalysisResultResponse: Complete analysis results with files and issues

    Raises:
        TaskNotFoundError: If task doesn't exist
        ValidationError: If task is not completed
    """
    logger.debug("Analysis results request", task_id=task_id)

    # Fetch task with analysis results
    result = await db.execute(
        select(Task)
        .options(
            selectinload(Task.pr_analysis)
            .selectinload(PRAnalysis.file_analyses)
            .selectinload(PRAnalysis.file_analyses)
        )
        .where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise TaskNotFoundError(task_id)

    # Check if task is completed
    if task.status != TaskStatus.COMPLETED:
        raise ValidationError(
            f"Task is not completed yet. Current status: {task.status.value}",
            field="task_status",
            value=task.status.value,
        )

    # Get the latest analysis result
    pr_analysis = None
    if task.pr_analysis:
        pr_analysis = task.pr_analysis

    if not pr_analysis:
        raise NotFoundError(
            "PR Analysis", f"No analysis results found for task {task_id}"
        )

    # For now, return a simplified response until we have full analysis data
    from app.api.schemas import AnalysisSummary

    # Create basic summary
    summary = AnalysisSummary(
        total_files=0,
        total_lines_added=0,
        total_lines_removed=0,
        total_issues=0,
        critical_issues=0,
        high_issues=0,
        medium_issues=0,
        low_issues=0,
        languages_detected=[],
        overall_score=None,
    )

    return PRAnalysisResultsResponse(
        success=True,
        message="Analysis results retrieved successfully",
        task_id=task.id,
        status=pr_analysis.status if pr_analysis else AnalysisStatus.PENDING,
        github_repo=task.repo_url,
        pr_number=task.pr_number,
        analysis_started_at=task.started_at or task.created_at,
        analysis_completed_at=task.completed_at,
        summary=summary,
        files=[],  # Will be populated with actual file analysis data
        metadata={},  # TODO: Properly handle metadata extraction
    )


# Helper functions
def _is_valid_github_url(url: str) -> bool:
    """
    Validate GitHub repository URL format.

    Args:
        url: Repository URL to validate

    Returns:
        bool: True if URL is valid GitHub repository URL
    """
    import re

    github_patterns = [
        r"^https://github\.com/[\w\-\.]+/[\w\-\.]+/?$",
        r"^git@github\.com:[\w\-\.]+/[\w\-\.]+\.git$",
    ]

    return any(re.match(pattern, url.strip()) for pattern in github_patterns)


def _extract_repo_info(url: str) -> tuple[str, str]:
    """
    Extract owner and repository name from GitHub URL.

    Args:
        url: GitHub repository URL

    Returns:
        tuple[str, str]: (owner, repo_name)

    Raises:
        ValueError: If URL format is invalid
    """
    import re

    # Handle HTTPS URLs
    https_match = re.match(
        r"https://github\.com/([\w\-\.]+)/([\w\-\.]+)/?$", url.strip()
    )
    if https_match:
        return https_match.group(1), https_match.group(2)

    # Handle SSH URLs
    ssh_match = re.match(r"git@github\.com:([\w\-\.]+)/([\w\-\.]+)\.git$", url.strip())
    if ssh_match:
        return ssh_match.group(1), ssh_match.group(2)

    raise ValueError("Invalid GitHub repository URL format")
