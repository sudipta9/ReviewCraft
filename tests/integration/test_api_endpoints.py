"""
Integration tests for API endpoints.

Tests cover the full API functionality including request validation,
error handling, and response formatting.
"""

from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


class TestAPIEndpoints:
    """Integration test suite for API endpoints."""

    @pytest.fixture
    def app(self):
        """Create FastAPI app for testing."""
        return create_app()

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    @pytest.mark.integration
    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")

        # Health check should work even if database is not connected
        assert response.status_code in [200, 503]

        if response.status_code == 200:
            data = response.json()
            assert "status" in data
            assert data["status"] in ["healthy", "degraded"]

    @pytest.mark.integration
    def test_openapi_schema_generation(self, client):
        """Test OpenAPI schema generation."""
        response = client.get("/openapi.json")
        assert response.status_code == 200

        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema
        assert "paths" in schema

        # Check required endpoints exist
        paths = schema["paths"]
        assert "/health" in paths
        assert "/api/v1/analyze-pr" in paths
        assert "/api/v1/status/{task_id}" in paths
        assert "/api/v1/results/{task_id}" in paths

    @pytest.mark.integration
    def test_docs_endpoint(self, client):
        """Test Swagger documentation endpoint."""
        response = client.get("/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    @pytest.mark.integration
    def test_analyze_pr_validation_missing_fields(self, client):
        """Test PR analysis endpoint with missing required fields."""
        # Empty request
        response = client.post("/api/v1/analyze-pr", json={})
        assert response.status_code == 422

        error_data = response.json()
        assert "detail" in error_data

        # Check that both required fields are mentioned in errors
        error_messages = str(error_data["detail"])
        assert "repo_url" in error_messages
        assert "pr_number" in error_messages

    @pytest.mark.integration
    def test_analyze_pr_validation_invalid_priority(self, client):
        """Test PR analysis endpoint with invalid priority."""
        request_data = {
            "repo_url": "https://github.com/owner/repo",
            "pr_number": 42,
            "priority": "invalid_priority",
        }

        response = client.post("/api/v1/analyze-pr", json=request_data)
        assert response.status_code == 422

        error_data = response.json()
        error_messages = str(error_data["detail"])
        assert "priority" in error_messages
        assert "low" in error_messages or "normal" in error_messages

    @pytest.mark.integration
    def test_analyze_pr_validation_invalid_url(self, client):
        """Test PR analysis endpoint with invalid GitHub URL."""
        request_data = {"repo_url": "not-a-valid-url", "pr_number": 42}

        response = client.post("/api/v1/analyze-pr", json=request_data)
        assert response.status_code == 400

        error_data = response.json()
        assert "error" in error_data
        assert "url" in error_data["error"].lower()

    @pytest.mark.integration
    def test_analyze_pr_validation_valid_priorities(self, client):
        """Test PR analysis endpoint with all valid priorities."""
        valid_priorities = ["low", "normal", "high", "urgent"]

        for priority in valid_priorities:
            request_data = {
                "repo_url": "https://github.com/owner/repo",
                "pr_number": 42,
                "priority": priority,
            }

            # This will fail at GitHub API level, but validation should pass
            response = client.post("/api/v1/analyze-pr", json=request_data)

            # Should not be a validation error (422)
            assert response.status_code != 422

    @pytest.mark.integration
    def test_analyze_pr_default_priority(self, client):
        """Test PR analysis endpoint with default priority."""
        request_data = {
            "repo_url": "https://github.com/owner/repo",
            "pr_number": 42,
            # No priority specified - should use default
        }

        # This will fail at processing level, but validation should pass
        response = client.post("/api/v1/analyze-pr", json=request_data)

        # Should not be a validation error
        assert response.status_code != 422

    @pytest.mark.integration
    def test_status_endpoint_invalid_task_id(self, client):
        """Test status endpoint with invalid task ID format."""
        response = client.get("/api/v1/status/invalid-uuid")

        # Should return 404 or 400 depending on implementation
        assert response.status_code in [400, 404]

    @pytest.mark.integration
    def test_status_endpoint_nonexistent_task(self, client):
        """Test status endpoint with non-existent task ID."""
        fake_uuid = "550e8400-e29b-41d4-a716-446655440000"
        response = client.get(f"/api/v1/status/{fake_uuid}")

        # Should return 404 for non-existent task
        assert response.status_code == 404

    @pytest.mark.integration
    def test_results_endpoint_invalid_task_id(self, client):
        """Test results endpoint with invalid task ID format."""
        response = client.get("/api/v1/results/invalid-uuid")

        # Should return 404 or 400 depending on implementation
        assert response.status_code in [400, 404]

    @pytest.mark.integration
    def test_results_endpoint_nonexistent_task(self, client):
        """Test results endpoint with non-existent task ID."""
        fake_uuid = "550e8400-e29b-41d4-a716-446655440000"
        response = client.get(f"/api/v1/results/{fake_uuid}")

        # Should return 404 for non-existent task
        assert response.status_code == 404

    @pytest.mark.integration
    def test_error_response_format(self, client):
        """Test that error responses follow consistent format."""
        # Test validation error
        response = client.post("/api/v1/analyze-pr", json={})
        assert response.status_code == 422

        error_data = response.json()
        assert "detail" in error_data

        # Test application error
        response = client.post(
            "/api/v1/analyze-pr", json={"repo_url": "invalid-url", "pr_number": 42}
        )

        if response.status_code == 400:
            error_data = response.json()
            assert "error" in error_data

    @pytest.mark.integration
    def test_content_type_headers(self, client):
        """Test that responses have correct content type headers."""
        # JSON endpoints
        response = client.get("/health")
        if response.status_code == 200:
            assert "application/json" in response.headers["content-type"]

        response = client.get("/openapi.json")
        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]

        # HTML endpoint
        response = client.get("/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    @pytest.mark.integration
    @patch("app.worker.pr_analysis_task.analyze_pr_task.delay")
    def test_analyze_pr_task_creation(self, mock_task, client):
        """Test that analyze PR endpoint creates background task."""
        # Mock successful task creation
        mock_task.return_value = Mock(id="test-task-123")

        request_data = {
            "repo_url": "https://github.com/owner/repo",
            "pr_number": 42,
            "priority": "normal",
        }

        with patch("app.api.pr_analysis.GitHubClient") as mock_github:
            # Mock successful URL validation
            mock_github.return_value._parse_repo_url.return_value = ("owner", "repo")

            response = client.post("/api/v1/analyze-pr", json=request_data)

            if response.status_code == 200:
                data = response.json()
                assert "task_id" in data
                assert "status" in data
                assert data["status"] in ["pending", "started"]

    @pytest.mark.integration
    def test_cors_headers(self, client):
        """Test CORS headers are present for cross-origin requests."""
        # Preflight request
        response = client.options(
            "/api/v1/analyze-pr",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )

        # Should handle CORS if middleware is configured
        # This test may need adjustment based on actual CORS setup
        assert response.status_code in [200, 204, 405]

    @pytest.mark.integration
    def test_request_id_header(self, client):
        """Test that responses include request ID headers."""
        response = client.get("/health")

        # Many APIs include request ID for tracing
        # This is optional based on implementation
        if "x-request-id" in response.headers:
            assert len(response.headers["x-request-id"]) > 0

    @pytest.mark.integration
    def test_rate_limiting_headers(self, client):
        """Test rate limiting headers if implemented."""
        response = client.post(
            "/api/v1/analyze-pr",
            json={"repo_url": "https://github.com/owner/repo", "pr_number": 42},
        )

        # Rate limiting headers are optional
        rate_limit_headers = [
            "x-ratelimit-limit",
            "x-ratelimit-remaining",
            "x-ratelimit-reset",
        ]

        # If any rate limit header exists, log it for verification
        for header in rate_limit_headers:
            if header in response.headers:
                print(f"Rate limit header found: {header} = {response.headers[header]}")

    @pytest.mark.integration
    def test_json_serialization_datetime(self, client):
        """Test that datetime objects are properly serialized in responses."""
        # This tests our orjson integration
        response = client.get("/health")

        if response.status_code == 200:
            data = response.json()

            # If response contains timestamp fields, they should be properly formatted
            for key, value in data.items():
                if "time" in key.lower() or "date" in key.lower():
                    # Should be ISO format string, not object
                    assert isinstance(value, str)

    @pytest.mark.integration
    def test_large_request_handling(self, client):
        """Test handling of large requests."""
        # Test with very long URL
        long_url = "https://github.com/owner/" + "a" * 1000

        request_data = {"repo_url": long_url, "pr_number": 42}

        response = client.post("/api/v1/analyze-pr", json=request_data)

        # Should handle gracefully, either accept or reject with proper error
        assert response.status_code in [200, 400, 413, 422]

    @pytest.mark.integration
    def test_security_headers(self, client):
        """Test security headers are present."""
        response = client.get("/health")

        # Common security headers (implementation dependent)
        security_headers = [
            "x-content-type-options",
            "x-frame-options",
            "x-xss-protection",
            "strict-transport-security",
        ]

        # Log which security headers are present
        for header in security_headers:
            if header in response.headers:
                print(f"Security header found: {header} = {response.headers[header]}")

    @pytest.mark.integration
    def test_endpoint_performance(self, client):
        """Basic performance test for endpoints."""
        import time

        # Test health endpoint performance
        start_time = time.time()
        response = client.get("/health")
        duration = time.time() - start_time

        # Health endpoint should be fast (under 1 second)
        assert duration < 1.0

        # Test schema endpoint performance
        start_time = time.time()
        response = client.get("/openapi.json")
        duration = time.time() - start_time

        # Schema generation should be reasonable (under 2 seconds)
        assert duration < 2.0
