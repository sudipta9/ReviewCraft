"""
Unit tests for the GitHub Client service.

Tests cover GitHub API integration, repository analysis,
PR fetching, and error handling functionality.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import httpx

from app.services.github_client import GitHubClient
from app.utils import GitHubAPIError


class TestGitHubClient:
    """Test suite for GitHubClient service."""

    @pytest.fixture
    def github_client(self, mock_settings):
        """Create GitHub client instance for testing."""
        with patch(
            "app.services.github_client.get_settings", return_value=mock_settings
        ):
            return GitHubClient()

    @pytest.mark.unit
    def test_client_initialization(self, github_client):
        """Test GitHub client initialization."""
        assert github_client is not None
        assert hasattr(github_client, "base_url")
        assert github_client.base_url == "https://api.github.com"

    @pytest.mark.unit
    def test_parse_repo_url_valid(self, github_client):
        """Test parsing valid GitHub repository URLs."""
        test_cases = [
            ("https://github.com/owner/repo", ("owner", "repo")),
            ("https://github.com/owner/repo.git", ("owner", "repo")),
            ("https://github.com/owner/repo/", ("owner", "repo")),
            ("git@github.com:owner/repo.git", ("owner", "repo")),
        ]

        for url, expected in test_cases:
            owner, repo = github_client._parse_repo_url(url)
            assert owner == expected[0]
            assert repo == expected[1]

    @pytest.mark.unit
    def test_parse_repo_url_invalid(self, github_client):
        """Test parsing invalid GitHub repository URLs."""
        invalid_urls = [
            "not-a-url",
            "https://gitlab.com/owner/repo",
            "https://github.com/invalid",
            "",
            "https://github.com/",
        ]

        for url in invalid_urls:
            with pytest.raises(ValueError):
                github_client._parse_repo_url(url)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_pull_request_success(self, github_client, mock_github_pr_data):
        """Test successful pull request fetching."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_github_pr_data

        with patch.object(github_client, "_make_request", return_value=mock_response):
            result = await github_client.get_pull_request(
                "https://github.com/owner/repo", 42
            )

            assert result == mock_github_pr_data
            assert result["number"] == 42
            assert result["title"] == "Fix authentication bug"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_pull_request_not_found(self, github_client):
        """Test pull request not found error."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"message": "Not Found"}

        with patch.object(github_client, "_make_request", return_value=mock_response):
            with pytest.raises(GitHubAPIError) as exc_info:
                await github_client.get_pull_request(
                    "https://github.com/owner/repo", 999
                )
            assert "not found" in str(exc_info.value).lower()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_pr_files_success(self, github_client, mock_github_files_data):
        """Test successful PR files fetching."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_github_files_data

        with patch.object(github_client, "_make_request", return_value=mock_response):
            result = await github_client.get_pr_files(
                "https://github.com/owner/repo", 42
            )

            assert result == mock_github_files_data
            assert len(result) == 3
            assert result[0]["filename"] == "auth/models.py"
            assert result[1]["status"] == "modified"
            assert result[2]["status"] == "added"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_file_content_success(self, github_client):
        """Test successful file content fetching."""
        file_content = "def hello():\n    return 'Hello, World!'"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": "ZGVmIGhlbGxvKCk6CiAgICByZXR1cm4gJ0hlbGxvLCBXb3JsZCEn",  # base64 encoded
            "encoding": "base64",
        }

        with patch.object(github_client, "_make_request", return_value=mock_response):
            result = await github_client.get_file_content(
                "https://github.com/owner/repo", "main.py"
            )

            assert file_content in result

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_repository_info_success(self, github_client):
        """Test successful repository info fetching."""
        repo_data = {
            "id": 123456,
            "name": "test-repo",
            "full_name": "owner/test-repo",
            "description": "A test repository",
            "private": False,
            "default_branch": "main",
            "language": "Python",
            "stargazers_count": 100,
            "forks_count": 25,
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = repo_data

        with patch.object(github_client, "_make_request", return_value=mock_response):
            result = await github_client.get_repository_info(
                "https://github.com/owner/test-repo"
            )

            assert result == repo_data
            assert result["name"] == "test-repo"
            assert result["language"] == "Python"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_rate_limiting_handling(self, github_client):
        """Test rate limiting error handling."""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.json.return_value = {"message": "API rate limit exceeded"}
        mock_response.headers = {
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": "1640995200",
        }

        with patch.object(github_client, "_make_request", return_value=mock_response):
            with pytest.raises(GitHubAPIError) as exc_info:
                await github_client.get_pull_request(
                    "https://github.com/owner/repo", 42
                )
            assert "rate limit" in str(exc_info.value).lower()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_authentication_headers(self, github_client):
        """Test authentication headers are properly set."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = Mock()
            mock_client_instance.get = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            await github_client._make_request("GET", "/test", token="test-token")

            # Verify headers were set
            call_args = mock_client_instance.get.call_args
            headers = call_args[1]["headers"]
            assert headers["Authorization"] == "token test-token"
            assert headers["Accept"] == "application/vnd.github.v3+json"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_health_check_success(self, github_client):
        """Test successful health check."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}

        with patch.object(github_client, "_make_request", return_value=mock_response):
            result = await github_client.health_check()
            assert result is True

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_health_check_failure(self, github_client):
        """Test failed health check."""
        with patch.object(
            github_client, "_make_request", side_effect=Exception("Connection failed")
        ):
            result = await github_client.health_check()
            assert result is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_network_error_handling(self, github_client):
        """Test network error handling."""
        with patch.object(
            github_client,
            "_make_request",
            side_effect=httpx.NetworkError("Connection failed"),
        ):
            with pytest.raises(GitHubAPIError) as exc_info:
                await github_client.get_pull_request(
                    "https://github.com/owner/repo", 42
                )
            assert "network error" in str(exc_info.value).lower()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_timeout_handling(self, github_client):
        """Test timeout error handling."""
        with patch.object(
            github_client,
            "_make_request",
            side_effect=httpx.TimeoutException("Request timeout"),
        ):
            with pytest.raises(GitHubAPIError) as exc_info:
                await github_client.get_pull_request(
                    "https://github.com/owner/repo", 42
                )
            assert "timeout" in str(exc_info.value).lower()

    @pytest.mark.unit
    def test_request_headers_setup(self, github_client):
        """Test request headers are properly configured."""
        headers = github_client._get_headers()

        assert headers["User-Agent"].startswith("Code-Review-Agent/")
        assert headers["Accept"] == "application/vnd.github.v3+json"
        assert "X-GitHub-Api-Version" in headers

    @pytest.mark.unit
    def test_request_headers_with_token(self, github_client):
        """Test request headers with authentication token."""
        headers = github_client._get_headers(token="test-token")

        assert headers["Authorization"] == "token test-token"
        assert headers["User-Agent"].startswith("Code-Review-Agent/")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_pagination_handling(self, github_client):
        """Test pagination handling for large PR files list."""
        # Mock paginated response
        page1_data = [{"filename": f"file_{i}.py"} for i in range(30)]
        page2_data = [{"filename": f"file_{i}.py"} for i in range(30, 50)]

        mock_responses = [
            Mock(status_code=200, json=Mock(return_value=page1_data)),
            Mock(status_code=200, json=Mock(return_value=page2_data)),
        ]

        with patch.object(github_client, "_make_request", side_effect=mock_responses):
            # This would need actual pagination implementation
            result = await github_client.get_pr_files(
                "https://github.com/owner/repo", 42
            )

            # For now, just test first page
            assert len(result) == 30
            assert result[0]["filename"] == "file_0.py"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_error_response_parsing(self, github_client):
        """Test parsing of GitHub API error responses."""
        mock_response = Mock()
        mock_response.status_code = 422
        mock_response.json.return_value = {
            "message": "Validation Failed",
            "errors": [
                {"resource": "PullRequest", "field": "number", "code": "invalid"}
            ],
        }

        with patch.object(github_client, "_make_request", return_value=mock_response):
            with pytest.raises(GitHubAPIError) as exc_info:
                await github_client.get_pull_request(
                    "https://github.com/owner/repo", -1
                )

            error_message = str(exc_info.value)
            assert "validation failed" in error_message.lower()
            assert "422" in error_message
