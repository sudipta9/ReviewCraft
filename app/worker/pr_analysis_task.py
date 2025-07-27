"""
PR Analysis Celery Task

This module contains the Celery task for performing autonomous code review
analysis on GitHub pull requests.

The task orchestrates the entire analysis workflow:
1. Fetch PR data from GitHub
2. Analyze code changes using AI agents
3. Generate structured feedback
4. Store results in database
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Optional

from app.models import PRAnalysis, Task, TaskStatus, AnalysisStatus
from app.utils import (
    GitHubAPIError,
    TaskFailedError,
    get_logger,
    log_task_failure,
    log_task_start,
    log_task_success,
)
from app.worker.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(
    bind=True,
    name="analyze_pr_task",
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
)
def analyze_pr_task(
    self,
    task_id: str,
    repo_url: str,
    pr_number: int,
    github_token: Optional[str] = None,
) -> Dict:
    """
    Analyze a GitHub pull request using AI agents.

    Args:
        self: Celery task instance (bound)
        task_id: Database task ID
        repo_url: GitHub repository URL
        pr_number: Pull request number
        github_token: Optional GitHub token for authentication

    Returns:
        Dict: Analysis results summary

    Raises:
        TaskFailedError: If analysis fails
        GitHubAPIError: If GitHub API call fails
        GitHubPRNotFoundError: If PR doesn't exist
    """
    start_time = time.time()

    log_task_start(
        task_id=self.request.id,
        task_name="analyze_pr_task",
        repo_url=repo_url,
        pr_number=pr_number,
        database_task_id=task_id,
    )

    try:
        # Update task progress
        self.update_state(
            state="PROGRESS",
            meta={
                "progress": 0,
                "stage": "initializing",
                "message": "Starting PR analysis...",
            },
        )

        # Run the async analysis workflow
        result = asyncio.run(
            _analyze_pr_async(
                task_id=task_id,
                repo_url=repo_url,
                pr_number=pr_number,
                github_token=github_token,
                celery_task=self,
            )
        )

        duration = time.time() - start_time

        log_task_success(
            task_id=self.request.id,
            task_name="analyze_pr_task",
            duration_seconds=duration,
            database_task_id=task_id,
            total_files=result.get("total_files", 0),
            total_issues=result.get("total_issues", 0),
        )

        return result

    except Exception as e:
        duration = time.time() - start_time

        log_task_failure(
            task_id=self.request.id,
            task_name="analyze_pr_task",
            error=e,
            duration_seconds=duration,
            database_task_id=task_id,
        )

        # Update database task status
        asyncio.run(_update_task_failed(task_id, str(e)))

        # Re-raise for Celery retry logic
        raise TaskFailedError(task_id, str(e))


async def _analyze_pr_async(
    task_id: str,
    repo_url: str,
    pr_number: int,
    github_token: Optional[str],
    celery_task,
) -> Dict:
    """
    Async workflow for PR analysis.

    Args:
        task_id: Database task ID
        repo_url: GitHub repository URL
        pr_number: Pull request number
        github_token: Optional GitHub token
        celery_task: Celery task instance for progress updates

    Returns:
        Dict: Analysis results
    """
    from app.database import db_manager
    from app.services.github_client import GitHubClient
    from app.services.ai_agent import AIAgent
    from app.services.code_analyzer import CodeAnalyzer

    # Update progress: Fetching PR data
    celery_task.update_state(
        state="PROGRESS",
        meta={
            "progress": 10,
            "stage": "fetching_pr_data",
            "message": "Fetching PR data from GitHub...",
        },
    )

    # Step 1: Initialize services
    github_client = GitHubClient(token=github_token)
    ai_agent = AIAgent()
    code_analyzer = CodeAnalyzer()

    # Step 2: Fetch PR data
    try:
        pr_data = await github_client.get_pull_request(repo_url, pr_number)
        files_data = await github_client.get_pr_files(repo_url, pr_number)
    except Exception as e:
        await _update_task_failed(task_id, f"Failed to fetch PR data: {str(e)}")
        raise GitHubAPIError(f"Failed to fetch PR data: {str(e)}")

    # Update progress: Analyzing files
    celery_task.update_state(
        state="PROGRESS",
        meta={
            "progress": 30,
            "stage": "analyzing_files",
            "message": f"Analyzing {len(files_data)} files...",
        },
    )

    # Step 3: Update task status in database
    async with db_manager.get_session() as session:
        # Update task status
        from sqlalchemy import update

        await session.execute(
            update(Task)
            .where(Task.id == task_id)
            .values(
                status=TaskStatus.PROCESSING,
                estimated_completion_time=datetime.utcnow() + timedelta(minutes=5),
            )
        )

        # Create PR analysis record
        pr_analysis = PRAnalysis(
            task_id=task_id,
            status=AnalysisStatus.IN_PROGRESS,
            pr_title=pr_data.get("title", ""),
            pr_description=pr_data.get("body", ""),
            pr_author=pr_data.get("user", {}).get("login", ""),
            base_branch=pr_data.get("base", {}).get("ref", ""),
            head_branch=pr_data.get("head", {}).get("ref", ""),
            total_files=len(files_data),
            files_changed=len(files_data),
            metadata={
                "pr_url": pr_data.get("html_url"),
                "pr_created_at": pr_data.get("created_at"),
                "pr_updated_at": pr_data.get("updated_at"),
            },
        )

        session.add(pr_analysis)
        await session.commit()
        await session.refresh(pr_analysis)

    # Step 4: Analyze each file
    file_analyses = []
    total_issues = 0

    for i, file_data in enumerate(files_data):
        # Update progress
        progress = 30 + int((i / len(files_data)) * 50)
        celery_task.update_state(
            state="PROGRESS",
            meta={
                "progress": progress,
                "stage": "analyzing_files",
                "message": f"Analyzing file {i+1}/{len(files_data)}: {file_data.get('filename', 'unknown')}",
            },
        )

        try:
            # Analyze individual file
            file_analysis = await code_analyzer.analyze_file(
                file_data=file_data, pr_context=pr_data, ai_agent=ai_agent
            )

            file_analysis.pr_analysis_id = pr_analysis.id
            file_analyses.append(file_analysis)

            # Count issues
            if hasattr(file_analysis, "issues"):
                total_issues += len(file_analysis.issues)

        except Exception as e:
            logger.warning(
                "Failed to analyze file",
                task_id=task_id,
                file=file_data.get("filename"),
                error=str(e),
            )
            # Continue with other files

    # Update progress: Generating summary
    celery_task.update_state(
        state="PROGRESS",
        meta={
            "progress": 85,
            "stage": "generating_summary",
            "message": "Generating analysis summary...",
        },
    )

    # Step 5: Generate AI summary and recommendations
    try:
        summary = await ai_agent.generate_summary(
            pr_data=pr_data, file_analyses=file_analyses, total_issues=total_issues
        )
    except Exception as e:
        logger.warning("Failed to generate AI summary", task_id=task_id, error=str(e))
        summary = {
            "overall_quality": "unknown",
            "recommendations": ["Analysis summary generation failed"],
            "critical_issues": 0,
        }

    # Step 6: Save results to database
    celery_task.update_state(
        state="PROGRESS",
        meta={
            "progress": 95,
            "stage": "saving_results",
            "message": "Saving analysis results...",
        },
    )

    async with db_manager.get_session() as session:
        # Update PR analysis with results
        from sqlalchemy import update

        critical_issues = sum(
            1
            for fa in file_analyses
            for issue in getattr(fa, "issues", [])
            if getattr(issue, "severity", "").lower() == "critical"
        )

        await session.execute(
            update(PRAnalysis)
            .where(PRAnalysis.id == pr_analysis.id)
            .values(
                status=AnalysisStatus.COMPLETED,
                total_issues=total_issues,
                critical_issues=critical_issues,
                summary=summary,
                overall_score=summary.get("overall_score", 75),
                recommendations=summary.get("recommendations", []),
            )
        )

        # Save file analyses
        for file_analysis in file_analyses:
            session.add(file_analysis)

        # Update main task status
        await session.execute(
            update(Task)
            .where(Task.id == task_id)
            .values(status=TaskStatus.COMPLETED, completed_at=datetime.utcnow())
        )

        await session.commit()

    # Final progress update
    celery_task.update_state(
        state="SUCCESS",
        meta={
            "progress": 100,
            "stage": "completed",
            "message": "Analysis completed successfully!",
        },
    )

    return {
        "task_id": task_id,
        "pr_analysis_id": pr_analysis.id,
        "total_files": len(files_data),
        "total_issues": total_issues,
        "critical_issues": critical_issues,
        "overall_score": summary.get("overall_score", 75),
        "status": "completed",
    }


async def _update_task_failed(task_id: str, error_message: str) -> None:
    """Update task status to failed in database."""
    from app.database import db_manager
    from sqlalchemy import update

    async with db_manager.get_session() as session:
        await session.execute(
            update(Task)
            .where(Task.id == task_id)
            .values(
                status=TaskStatus.FAILED,
                error_message=error_message,
                completed_at=datetime.utcnow(),
            )
        )
        await session.commit()
