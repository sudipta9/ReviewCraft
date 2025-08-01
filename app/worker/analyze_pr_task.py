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
import concurrent.futures
import time
from datetime import datetime
from typing import Dict, Optional

from app.models import AnalysisStatus, PRAnalysis, Task, TaskStatus
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


def run_async_in_celery(coro):
    """
    Run async coroutine in Celery worker, handling event loop conflicts.

    This function properly manages event loops to avoid the "Event loop is closed"
    error that occurs when multiple Celery tasks use asyncio.run().
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # No event loop in current thread, create a new one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        # If loop is already running (in some Celery setups), we need to run in executor
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()
    else:
        # Loop is not running, we can use run_until_complete
        return loop.run_until_complete(coro)


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
        # Use helper function to avoid event loop conflicts in Celery
        result = run_async_in_celery(
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
        run_async_in_celery(_update_task_failed(task_id, str(e)))

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
    from app.services.ai_agent import AIAgent
    from app.services.code_analyzer import CodeAnalyzer
    from app.services.github_client import GitHubClient

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

    try:
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
                    started_at=datetime.now(),
                )
            )

            # Create PR analysis record
            pr_analysis = PRAnalysis(
                task_id=task_id,
                status=AnalysisStatus.IN_PROGRESS,
                pr_url=pr_data.get("html_url", ""),
                base_branch=pr_data.get("base", {}).get("ref", "main"),
                head_branch=pr_data.get("head", {}).get("ref", "feature"),
                base_sha=pr_data.get("base", {}).get("sha", ""),
                head_sha=pr_data.get("head", {}).get("sha", ""),
                analysis_started_at=datetime.now(),
                total_files_analyzed=len(files_data),
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

                # Set pr_analysis_id for all issues in this file analysis
                if hasattr(file_analysis, "issues"):
                    for issue in file_analysis.issues:
                        issue.pr_analysis_id = pr_analysis.id

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
            logger.warning(
                "Failed to generate AI summary", task_id=task_id, error=str(e)
            )
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
                    analysis_completed_at=datetime.now(),
                    total_issues_found=total_issues,
                    critical_issues=critical_issues,
                    summary=str(summary.get("overall_quality", "Analysis completed")),
                    quality_score=float(summary.get("overall_score", 75)),
                    recommendations=summary.get("recommendations", []),
                )
            )

            # Save file analyses
            for file_analysis in file_analyses:
                # Add the file analysis to the session first
                session.add(file_analysis)
                # The issues should be automatically handled by the relationship,
                # but we need to ensure pr_analysis_id is set on each issue
                # (this was already done in the analysis loop above)

            # Update main task status
            await session.execute(
                update(Task)
                .where(Task.id == task_id)
                .values(status=TaskStatus.COMPLETED, completed_at=datetime.now())
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

    finally:
        # Always close the GitHub client to prevent resource leaks
        await github_client.client.aclose()


async def _update_task_failed(task_id: str, error_message: str) -> None:
    """Update task status to failed in database."""
    from sqlalchemy import update

    from app.database import db_manager

    async with db_manager.get_session() as session:
        await session.execute(
            update(Task)
            .where(Task.id == task_id)
            .values(
                status=TaskStatus.FAILED,
                error_message=error_message,
                completed_at=datetime.now(),
            )
        )
        await session.commit()
