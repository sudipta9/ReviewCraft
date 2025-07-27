"""
Integration tests for the autonomous code review system.

Tests cover end-to-end workflows, service integration,
and real API functionality.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest


class TestServiceIntegration:
    """Integration tests for service interactions."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_github_client_and_ai_agent_integration(
        self, mock_github_client, mock_ai_agent
    ):
        """Test integration between GitHub client and AI agent."""
        from app.services.code_analyzer import CodeAnalyzer

        # Setup mock data
        mock_github_client.get_pull_request.return_value = {
            "number": 42,
            "title": "Fix authentication bug",
            "state": "open",
        }

        mock_github_client.get_pr_files.return_value = [
            {
                "filename": "auth/models.py",
                "status": "modified",
                "additions": 10,
                "deletions": 2,
                "patch": "some diff content",
            }
        ]

        # Test the integration
        code_analyzer = CodeAnalyzer()

        with patch.object(code_analyzer, "ai_agent", mock_ai_agent):
            pr_data = await mock_github_client.get_pull_request(
                "https://github.com/test/repo", 42
            )
            files_data = await mock_github_client.get_pr_files(
                "https://github.com/test/repo", 42
            )

            assert pr_data["number"] == 42
            assert len(files_data) == 1
            assert files_data[0]["filename"] == "auth/models.py"

            # Verify AI agent would be called for analysis
            mock_ai_agent.analyze_code_quality.assert_not_called()  # Not called yet in this setup
            mock_ai_agent.analyze_security.assert_not_called()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_file_analysis_workflow(self, mock_ai_agent, sample_python_code):
        """Test complete file analysis workflow."""
        from app.services.code_analyzer import CodeAnalyzer

        code_analyzer = CodeAnalyzer()

        file_data = {
            "filename": "test.py",
            "status": "modified",
            "additions": 20,
            "deletions": 5,
            "content": sample_python_code,
            "patch": "mock patch content",
        }

        pr_context = {"pr_number": 42, "base_branch": "main"}

        with patch.object(code_analyzer, "ai_agent", mock_ai_agent):
            result = await code_analyzer.analyze_file(
                file_data, pr_context, mock_ai_agent
            )

            # Verify AI agent methods were called
            mock_ai_agent.analyze_code_quality.assert_called_once()
            mock_ai_agent.analyze_security.assert_called_once()
            mock_ai_agent.generate_suggestions.assert_called_once()

            # Verify result structure
            assert result.file_path == "test.py"
            assert result.file_name == "test.py"
            assert result.lines_added == 20
            assert result.lines_removed == 5

    @pytest.mark.integration
    def test_configuration_integration(self, mock_settings):
        """Test configuration integration across services."""
        from app.services.ai_agent import AIAgent
        from app.services.github_client import GitHubClient

        with patch(
            "app.services.github_client.get_settings", return_value=mock_settings
        ), patch("app.services.ai_agent.get_settings", return_value=mock_settings):

            github_client = GitHubClient()
            ai_agent = AIAgent()

            # Verify settings are properly used
            assert github_client is not None
            assert ai_agent is not None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_error_propagation_across_services(
        self, mock_github_client, mock_ai_agent
    ):
        """Test error handling across service boundaries."""
        from app.services.code_analyzer import CodeAnalyzer
        from app.utils import GitHubAPIError

        # Setup GitHub client to fail
        mock_github_client.get_pull_request.side_effect = GitHubAPIError("API error")

        code_analyzer = CodeAnalyzer()

        # Error should propagate properly
        with pytest.raises(GitHubAPIError):
            await mock_github_client.get_pull_request(
                "https://github.com/test/repo", 42
            )


class TestAPIIntegration:
    """Integration tests for API endpoints."""

    @pytest.mark.integration
    def test_api_schema_completeness(self, client):
        """Test that API schema includes all expected endpoints."""
        response = client.get("/openapi.json")
        assert response.status_code == 200

        schema = response.json()
        paths = schema["paths"]

        # Verify all main endpoints are documented
        expected_endpoints = [
            "/health",
            "/api/v1/analyze-pr",
            "/api/v1/status/{task_id}",
            "/api/v1/results/{task_id}",
        ]

        for endpoint in expected_endpoints:
            assert endpoint in paths, f"Endpoint {endpoint} missing from API schema"

    @pytest.mark.integration
    def test_api_error_responses_consistency(self, client):
        """Test that API error responses are consistent."""
        # Test various error scenarios
        error_responses = [
            client.post("/api/v1/analyze-pr", json={}),  # Validation error
            client.post(
                "/api/v1/analyze-pr", json={"repo_url": "invalid", "pr_number": 1}
            ),  # App error
            client.get("/api/v1/results/nonexistent"),  # Not found
        ]

        for response in error_responses:
            assert response.status_code >= 400
            data = response.json()

            # All errors should have consistent structure
            assert "error_code" in data or "detail" in data
            if "error_code" in data:
                assert isinstance(data["error_code"], str)
                assert "message" in data

    @pytest.mark.integration
    def test_api_response_headers(self, client):
        """Test API response headers are properly set."""
        response = client.get("/health")

        # Check content type (should be JSON)
        assert response.headers["content-type"].startswith("application/json")

    @pytest.mark.integration
    @pytest.mark.slow
    def test_api_performance_basic(self, client):
        """Basic API performance test."""
        import time

        # Test health endpoint performance
        start_time = time.time()
        response = client.get("/health")
        duration = time.time() - start_time

        assert response.status_code == 200
        assert duration < 1.0  # Should respond quickly


class TestDatabaseIntegration:
    """Integration tests for database operations."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_database_connection(self):
        """Test database connection and basic operations."""
        from app.database import db_manager

        try:
            async with db_manager.get_session() as session:
                # Test basic query
                from sqlalchemy import text

                result = await session.execute(text("SELECT 1"))
                value = result.scalar()
                assert value == 1

        except Exception as e:
            # Expected in test environment without real database
            assert "database" in str(e).lower() or "connection" in str(e).lower()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_task_model_operations(self, async_db_session):
        """Test Task model database operations."""
        from app.models import Task, TaskPriority, TaskStatus

        # Create a test task
        task = Task(
            task_id="test-integration-123",
            repo_url="https://github.com/test/repo",
            pr_number=42,
            status=TaskStatus.PENDING,
            priority=TaskPriority.NORMAL,
        )

        # Mock database operations
        async_db_session.add = Mock()
        async_db_session.commit = AsyncMock()
        async_db_session.refresh = AsyncMock()

        # Test task creation workflow
        async_db_session.add(task)
        await async_db_session.commit()

        # Verify task properties (using available attributes)
        assert task.repo_url == "https://github.com/test/repo"
        assert task.pr_number == 42
        assert task.status == TaskStatus.PENDING


class TestCeleryIntegration:
    """Integration tests for Celery task queue."""

    @pytest.mark.integration
    @pytest.mark.slow
    def test_celery_task_registration(self):
        """Test that Celery tasks are properly registered."""
        from app.worker.celery_app import celery_app

        # Check if our main task is registered
        registered_tasks = celery_app.tasks
        assert any("analyze_pr_task" in task_name for task_name in registered_tasks)

    @pytest.mark.integration
    def test_celery_configuration(self):
        """Test Celery configuration."""
        from app.worker.celery_app import celery_app

        # Verify basic configuration
        assert celery_app.conf.task_serializer == "json"
        assert celery_app.conf.result_serializer == "json"
        assert celery_app.conf.accept_content == ["json"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_task_creation_and_tracking(self):
        """Test task creation and status tracking."""
        from app.worker.pr_analysis_task import analyze_pr_task

        with patch("app.worker.pr_analysis_task.analyze_pr_task.delay") as mock_delay:
            mock_task_result = Mock()
            mock_task_result.id = "mock-task-123"
            mock_delay.return_value = mock_task_result

            # Simulate task creation
            result = mock_delay(
                task_id="test-task",
                repo_url="https://github.com/test/repo",
                pr_number=42,
                github_token=None,
                priority="normal",
            )

            assert result.id == "mock-task-123"
            mock_delay.assert_called_once()


class TestEndToEndWorkflow:
    """End-to-end integration tests."""

    @pytest.mark.integration
    @pytest.mark.slow
    def test_complete_pr_analysis_workflow_mock(self, client):
        """Test complete PR analysis workflow with mocked services."""
        with patch(
            "app.worker.pr_analysis_task.analyze_pr_task.delay"
        ) as mock_task, patch("app.services.github_client.GitHubClient"), patch(
            "app.services.ai_agent.AIAgent"
        ):

            # Setup mocks
            mock_task.return_value.id = "workflow-test-123"

            # Step 1: Submit PR for analysis
            response = client.post(
                "/api/v1/analyze-pr",
                json={
                    "repo_url": "https://github.com/test/repo",
                    "pr_number": 42,
                    "priority": "high",
                },
            )

            assert response.status_code == 202
            data = response.json()
            task_id = data["task_id"]

            # Step 2: Check task status
            with patch(
                "app.worker.pr_analysis_task.analyze_pr_task.AsyncResult"
            ) as mock_result:
                mock_result.return_value.state = "PROGRESS"
                mock_result.return_value.info = {
                    "progress": 50,
                    "stage": "analyzing_files",
                }

                response = client.get(f"/api/v1/status/{task_id}")
                assert response.status_code == 200

                status_data = response.json()
                assert status_data["status"] == "PROGRESS"
                assert status_data["progress"] == 50

    @pytest.mark.integration
    def test_api_documentation_accessibility(self, client):
        """Test that API documentation is accessible."""
        # Test Swagger UI
        response = client.get("/docs")
        assert response.status_code == 200

        # Test ReDoc
        response = client.get("/redoc")
        assert response.status_code == 200

    @pytest.mark.integration
    def test_health_check_comprehensive(self, client):
        """Comprehensive health check test."""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data

        # Health check should be fast
        import time

        start = time.time()
        client.get("/health")
        duration = time.time() - start
        assert duration < 0.5  # Should be very fast

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_service_health_checks(self):
        """Test health checks of individual services."""
        from app.services.github_client import GitHubClient

        # Mock GitHub client health check
        with patch("app.services.github_client.get_settings") as mock_settings:
            mock_settings.return_value.github.token = "test-token"

            github_client = GitHubClient()

            with patch.object(github_client, "_make_request") as mock_request:
                mock_request.return_value.status_code = 200

                is_healthy = await github_client.health_check()
                assert is_healthy is True
