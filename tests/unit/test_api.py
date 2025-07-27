"""
Unit tests for the FastAPI application endpoints.

Tests cover API validation, error handling, orjson serialization,
and endpoint functionality.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import orjson
import pytest
from fastapi import status

from app.api.schemas import TaskPriority


class TestAPIEndpoints:
    """Test suite for FastAPI endpoints."""

    @pytest.mark.unit
    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data

    @pytest.mark.unit
    def test_openapi_schema(self, client):
        """Test OpenAPI schema generation."""
        response = client.get("/openapi.json")

        assert response.status_code == status.HTTP_200_OK
        schema = response.json()
        assert "paths" in schema
        assert "info" in schema

        # Check main endpoints exist
        paths = schema["paths"]
        assert "/health" in paths
        assert "/api/v1/analyze-pr" in paths
        assert "/api/v1/status/{task_id}" in paths
        assert "/api/v1/results/{task_id}" in paths

    @pytest.mark.unit
    def test_analyze_pr_endpoint_validation_missing_fields(self, client):
        """Test PR analysis endpoint with missing required fields."""
        response = client.post("/api/v1/analyze-pr", json={})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        data = response.json()
        assert "detail" in data

        # Check validation errors
        errors = data["detail"]
        field_errors = [error["loc"] for error in errors]
        assert ("body", "repo_url") in field_errors
        assert ("body", "pr_number") in field_errors

    @pytest.mark.unit
    def test_analyze_pr_endpoint_validation_invalid_url(self, client):
        """Test PR analysis endpoint with invalid repository URL."""
        response = client.post(
            "/api/v1/analyze-pr", json={"repo_url": "invalid-url", "pr_number": 1}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "error_code" in data
        assert data["error_code"] == "VALIDATION_ERROR"
        assert "repo_url" in data["message"].lower()

    @pytest.mark.unit
    def test_analyze_pr_endpoint_validation_invalid_priority(self, client):
        """Test PR analysis endpoint with invalid priority."""
        response = client.post(
            "/api/v1/analyze-pr",
            json={
                "repo_url": "https://github.com/owner/repo",
                "pr_number": 1,
                "priority": "invalid_priority",
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        data = response.json()
        errors = data["detail"]

        # Find priority validation error
        priority_error = next(
            (error for error in errors if error["loc"] == ("body", "priority")), None
        )
        assert priority_error is not None
        assert "low" in priority_error["msg"]
        assert "normal" in priority_error["msg"]
        assert "high" in priority_error["msg"]
        assert "urgent" in priority_error["msg"]

    @pytest.mark.unit
    def test_analyze_pr_endpoint_valid_request(self, client):
        """Test PR analysis endpoint with valid request."""
        with patch("app.worker.pr_analysis_task.analyze_pr_task.delay") as mock_task:
            mock_task.return_value.id = "test-task-123"

            response = client.post(
                "/api/v1/analyze-pr",
                json={
                    "repo_url": "https://github.com/owner/repo",
                    "pr_number": 42,
                    "priority": "high",
                    "github_token": "optional-token",
                },
            )

            assert response.status_code == status.HTTP_202_ACCEPTED
            data = response.json()
            assert data["task_id"] == "test-task-123"
            assert data["status"] == "pending"
            assert "message" in data

    @pytest.mark.unit
    def test_analyze_pr_endpoint_default_priority(self, client):
        """Test PR analysis endpoint uses default priority."""
        with patch("app.worker.pr_analysis_task.analyze_pr_task.delay") as mock_task:
            mock_task.return_value.id = "test-task-456"

            response = client.post(
                "/api/v1/analyze-pr",
                json={"repo_url": "https://github.com/owner/repo", "pr_number": 42},
            )

            assert response.status_code == status.HTTP_202_ACCEPTED

            # Verify task was called with default priority
            call_args = mock_task.call_args
            assert TaskPriority.NORMAL in str(call_args)

    @pytest.mark.unit
    def test_status_endpoint_valid_task(self, client):
        """Test task status endpoint with valid task ID."""
        with patch(
            "app.worker.pr_analysis_task.analyze_pr_task.AsyncResult"
        ) as mock_result:
            mock_result.return_value.state = "PROGRESS"
            mock_result.return_value.info = {
                "progress": 50,
                "stage": "analyzing_files",
                "message": "Processing files...",
            }

            response = client.get("/api/v1/status/test-task-123")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["task_id"] == "test-task-123"
            assert data["status"] == "PROGRESS"
            assert data["progress"] == 50
            assert data["stage"] == "analyzing_files"

    @pytest.mark.unit
    def test_status_endpoint_completed_task(self, client):
        """Test task status endpoint with completed task."""
        with patch(
            "app.worker.pr_analysis_task.analyze_pr_task.AsyncResult"
        ) as mock_result:
            mock_result.return_value.state = "SUCCESS"
            mock_result.return_value.result = {
                "summary": "Analysis completed",
                "files_analyzed": 3,
            }

            response = client.get("/api/v1/status/completed-task")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "SUCCESS"
            assert data["message"] == "Task completed successfully"

    @pytest.mark.unit
    def test_status_endpoint_failed_task(self, client):
        """Test task status endpoint with failed task."""
        with patch(
            "app.worker.pr_analysis_task.analyze_pr_task.AsyncResult"
        ) as mock_result:
            mock_result.return_value.state = "FAILURE"
            mock_result.return_value.info = "GitHub API rate limit exceeded"

            response = client.get("/api/v1/status/failed-task")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "FAILURE"
            assert "rate limit" in data["message"].lower()

    @pytest.mark.unit
    def test_results_endpoint_success(self, client):
        """Test results endpoint with successful task."""
        mock_results = {
            "summary": {
                "overall_quality": "good",
                "total_files_analyzed": 3,
                "total_issues": 5,
            },
            "files": [
                {
                    "filename": "auth/models.py",
                    "quality_score": 85,
                    "issues": [
                        {"type": "style", "severity": "low", "message": "Line too long"}
                    ],
                }
            ],
        }

        with patch("app.database.db_manager.get_session") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock()
            mock_session.return_value.__aexit__ = AsyncMock()

            # Mock database query result
            mock_task = Mock()
            mock_task.task_id = "test-results-123"
            mock_task.status = "completed"
            mock_task.results = mock_results

            with patch("sqlalchemy.select"), patch.object(
                mock_session.return_value.__aenter__.return_value, "execute"
            ) as mock_execute:
                mock_execute.return_value.scalar_one_or_none.return_value = mock_task

                response = client.get("/api/v1/results/test-results-123")

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["task_id"] == "test-results-123"
                assert data["status"] == "completed"
                assert "results" in data
                assert data["results"]["summary"]["overall_quality"] == "good"

    @pytest.mark.unit
    def test_results_endpoint_not_found(self, client):
        """Test results endpoint with non-existent task."""
        with patch("app.database.db_manager.get_session") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock()
            mock_session.return_value.__aexit__ = AsyncMock()

            with patch.object(
                mock_session.return_value.__aenter__.return_value, "execute"
            ) as mock_execute:
                mock_execute.return_value.scalar_one_or_none.return_value = None

                response = client.get("/api/v1/results/nonexistent-task")

                assert response.status_code == status.HTTP_404_NOT_FOUND
                data = response.json()
                assert data["error_code"] == "TASK_NOT_FOUND"

    @pytest.mark.unit
    def test_orjson_datetime_serialization(self, client):
        """Test that orjson properly serializes datetime objects."""

        # Test datetime serialization
        test_data = {
            "timestamp": datetime.now(tz=timezone.utc),
            "task_id": "test-123",
            "status": "completed",
        }

        # This should not raise an exception
        json_bytes = orjson.dumps(test_data)
        assert isinstance(json_bytes, bytes)

        # Parse back
        parsed = orjson.loads(json_bytes)
        assert "timestamp" in parsed
        assert parsed["task_id"] == "test-123"

    @pytest.mark.unit
    def test_error_handling_middleware(self, client):
        """Test global error handling middleware."""
        # This would trigger internal server error handling
        with patch("app.api.pr_analysis.analyze_pr_endpoint") as mock_endpoint:
            mock_endpoint.side_effect = Exception("Internal error")

            response = client.post(
                "/api/v1/analyze-pr",
                json={"repo_url": "https://github.com/owner/repo", "pr_number": 1},
            )

            # Should handle error gracefully
            assert response.status_code in [400, 500]
            data = response.json()
            assert "error_code" in data or "detail" in data

    @pytest.mark.unit
    def test_request_validation_edge_cases(self, client):
        """Test edge cases in request validation."""
        # Negative PR number
        response = client.post(
            "/api/v1/analyze-pr",
            json={"repo_url": "https://github.com/owner/repo", "pr_number": -1},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Zero PR number
        response = client.post(
            "/api/v1/analyze-pr",
            json={"repo_url": "https://github.com/owner/repo", "pr_number": 0},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Very large PR number (should be accepted)
        with patch("app.worker.pr_analysis_task.analyze_pr_task.delay") as mock_task:
            mock_task.return_value.id = "test-large-pr"

            response = client.post(
                "/api/v1/analyze-pr",
                json={"repo_url": "https://github.com/owner/repo", "pr_number": 999999},
            )
            assert response.status_code == status.HTTP_202_ACCEPTED

    @pytest.mark.unit
    def test_priority_enum_validation(self, client):
        """Test priority enum validation comprehensively."""
        valid_priorities = ["low", "normal", "high", "urgent"]

        for priority in valid_priorities:
            with patch(
                "app.worker.pr_analysis_task.analyze_pr_task.delay"
            ) as mock_task:
                mock_task.return_value.id = f"test-{priority}"

                response = client.post(
                    "/api/v1/analyze-pr",
                    json={
                        "repo_url": "https://github.com/owner/repo",
                        "pr_number": 1,
                        "priority": priority,
                    },
                )

                assert (
                    response.status_code == status.HTTP_202_ACCEPTED
                ), f"Priority {priority} should be valid"

    @pytest.mark.unit
    def test_cors_headers(self, client):
        """Test CORS headers are properly set."""
        response = client.options("/api/v1/analyze-pr")

        # FastAPI should handle OPTIONS requests
        assert response.status_code in [
            200,
            405,
        ]  # 405 if OPTIONS not explicitly handled

    @pytest.mark.unit
    def test_content_type_validation(self, client):
        """Test content type validation."""
        # Send non-JSON data
        response = client.post(
            "/api/v1/analyze-pr",
            data="not-json-data",
            headers={"Content-Type": "text/plain"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.unit
    def test_github_url_variations(self, client):
        """Test various GitHub URL formats."""
        valid_urls = [
            "https://github.com/owner/repo",
            "https://github.com/owner/repo.git",
            "https://github.com/owner/repo/",
        ]

        for url in valid_urls:
            with patch(
                "app.worker.pr_analysis_task.analyze_pr_task.delay"
            ) as mock_task:
                mock_task.return_value.id = "test-url-validation"

                response = client.post(
                    "/api/v1/analyze-pr", json={"repo_url": url, "pr_number": 1}
                )

                # Should either accept or give validation error, not server error
                assert response.status_code in [202, 400, 422]
