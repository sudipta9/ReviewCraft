"""
GitHub API Client

This module provides a comprehensive GitHub API client for fetching
pull request data, file contents, and repository information.

Features:
- Async HTTP client with proper error handling
- Rate limiting and retry logic
- Support for authenticated and unauthenticated requests
- Structured data parsing and validation
"""

import asyncio
import base64
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse

import httpx
from structlog import get_logger

from app.config import get_settings
from app.utils import GitHubAPIError

logger = get_logger(__name__)


class GitHubClient:
    """
    GitHub API client for fetching PR and repository data.

    This client handles authentication, rate limiting, and provides
    structured methods for accessing GitHub API endpoints.
    """

    def __init__(self, token: Optional[str] = None):
        """
        Initialize GitHub client.

        Args:
            token: Optional GitHub personal access token
        """
        self.settings = get_settings()
        self.token = token or self.settings.github.token
        self.base_url = "https://api.github.com"

        # Setup HTTP client with proper headers
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "CodeReview-Agent/1.0",
        }

        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        self.client = httpx.AsyncClient(
            headers=headers,
            timeout=30.0,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()

    def _parse_repo_url(self, repo_url: str) -> tuple[str, str]:
        """
        Parse repository URL to extract owner and repo name.

        Args:
            repo_url: GitHub repository URL (https://github.com/owner/repo)

        Returns:
            tuple: (owner, repo_name)

        Raises:
            GitHubAPIError: If URL format is invalid
        """
        try:
            parsed = urlparse(repo_url)
            if parsed.hostname != "github.com":
                raise GitHubAPIError(f"Invalid GitHub URL: {repo_url}")

            path_parts = parsed.path.strip("/").split("/")
            if len(path_parts) < 2:
                raise GitHubAPIError(f"Invalid GitHub repository path: {parsed.path}")

            owner, repo = path_parts[0], path_parts[1]

            # Remove .git suffix if present
            if repo.endswith(".git"):
                repo = repo[:-4]

            return owner, repo

        except Exception as e:
            raise GitHubAPIError(f"Failed to parse repository URL {repo_url}: {str(e)}")

    async def _make_request(
        self, endpoint: str, params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make authenticated request to GitHub API.

        Args:
            endpoint: API endpoint path
            params: Optional query parameters

        Returns:
            Dict: JSON response data

        Raises:
            GitHubAPIError: If request fails
            GitHubPRNotFoundError: If resource not found
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        try:
            logger.info("Making GitHub API request", endpoint=endpoint, url=url)

            response = await self.client.get(url, params=params or {})

            # Handle rate limiting
            if response.status_code == 403 and "rate limit" in response.text.lower():
                reset_time = response.headers.get("X-RateLimit-Reset")
                logger.warning("GitHub API rate limit exceeded", reset_time=reset_time)
                raise GitHubAPIError("GitHub API rate limit exceeded")

            # Handle not found
            if response.status_code == 404:
                logger.warning("GitHub resource not found", endpoint=endpoint, url=url)
                raise GitHubAPIError(f"Resource not found: {endpoint}")

            # Handle other HTTP errors
            response.raise_for_status()

            data = response.json()

            logger.info(
                "GitHub API request successful",
                endpoint=endpoint,
                status_code=response.status_code,
                response_size=len(response.content),
            )

            return data

        except httpx.HTTPError as e:
            logger.error("GitHub API HTTP error", endpoint=endpoint, error=str(e))
            raise GitHubAPIError(f"HTTP error calling GitHub API: {str(e)}")
        except Exception as e:
            logger.error("GitHub API unexpected error", endpoint=endpoint, error=str(e))
            raise GitHubAPIError(f"Unexpected error calling GitHub API: {str(e)}")

    async def get_pull_request(self, repo_url: str, pr_number: int) -> Dict[str, Any]:
        """
        Fetch pull request data.

        Args:
            repo_url: GitHub repository URL
            pr_number: Pull request number

        Returns:
            Dict: Pull request data

        Raises:
            GitHubAPIError: If request fails
            GitHubPRNotFoundError: If PR doesn't exist
        """
        owner, repo = self._parse_repo_url(repo_url)
        endpoint = f"repos/{owner}/{repo}/pulls/{pr_number}"

        logger.info(
            "Fetching pull request", owner=owner, repo=repo, pr_number=pr_number
        )

        pr_data = await self._make_request(endpoint)

        # Enhance with additional metadata
        pr_data["_metadata"] = {
            "owner": owner,
            "repo": repo,
            "fetched_at": asyncio.get_event_loop().time(),
        }

        logger.info(
            "Pull request fetched successfully",
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            title=pr_data.get("title", "")[:50],
            state=pr_data.get("state"),
            files_changed=pr_data.get("changed_files", 0),
        )

        return pr_data

    async def get_pr_files(self, repo_url: str, pr_number: int) -> List[Dict[str, Any]]:
        """
        Fetch files changed in a pull request.

        Args:
            repo_url: GitHub repository URL
            pr_number: Pull request number

        Returns:
            List[Dict]: List of file change data

        Raises:
            GitHubAPIError: If request fails
        """
        owner, repo = self._parse_repo_url(repo_url)
        endpoint = f"repos/{owner}/{repo}/pulls/{pr_number}/files"

        logger.info("Fetching PR files", owner=owner, repo=repo, pr_number=pr_number)

        # GitHub paginated response handling
        all_files = []
        page = 1
        per_page = 100  # Maximum allowed by GitHub

        while True:
            params = {"page": page, "per_page": per_page}
            files_data = await self._make_request(endpoint, params)

            if not files_data:
                break

            all_files.extend(files_data)

            # If we got less than per_page results, we've reached the end
            if len(files_data) < per_page:
                break

            page += 1

            # Safety limit to prevent infinite loops
            if page > 50:  # 5000 files max
                logger.warning(
                    "Reached maximum file pagination limit", total_files=len(all_files)
                )
                break

        logger.info(
            "PR files fetched successfully",
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            total_files=len(all_files),
        )

        return all_files

    async def get_file_content(
        self, repo_url: str, file_path: str, ref: str = "main"
    ) -> str:
        """
        Fetch file content from repository.

        Args:
            repo_url: GitHub repository URL
            file_path: Path to file in repository
            ref: Git reference (branch, commit, tag)

        Returns:
            str: File content

        Raises:
            GitHubAPIError: If request fails
        """
        owner, repo = self._parse_repo_url(repo_url)
        endpoint = f"repos/{owner}/{repo}/contents/{file_path}"

        params = {"ref": ref}

        logger.info(
            "Fetching file content",
            owner=owner,
            repo=repo,
            file_path=file_path,
            ref=ref,
        )

        try:
            file_data = await self._make_request(endpoint, params)

            # Decode base64 content
            if file_data.get("encoding") == "base64":
                content = base64.b64decode(file_data["content"]).decode("utf-8")
            else:
                content = file_data.get("content", "")

            logger.info(
                "File content fetched successfully",
                owner=owner,
                repo=repo,
                file_path=file_path,
                size=len(content),
            )

            return content

        except GitHubAPIError:
            logger.warning(
                "File not found", owner=owner, repo=repo, file_path=file_path, ref=ref
            )
            return ""  # Return empty string for missing files
        except Exception as e:
            logger.error("Failed to fetch file content", error=str(e))
            raise GitHubAPIError(f"Failed to fetch file content: {str(e)}")

    async def get_repository_info(self, repo_url: str) -> Dict[str, Any]:
        """
        Fetch repository information.

        Args:
            repo_url: GitHub repository URL

        Returns:
            Dict: Repository data

        Raises:
            GitHubAPIError: If request fails
        """
        owner, repo = self._parse_repo_url(repo_url)
        endpoint = f"repos/{owner}/{repo}"

        logger.info("Fetching repository info", owner=owner, repo=repo)

        repo_data = await self._make_request(endpoint)

        logger.info(
            "Repository info fetched successfully",
            owner=owner,
            repo=repo,
            language=repo_data.get("language"),
            stars=repo_data.get("stargazers_count", 0),
        )

        return repo_data

    async def health_check(self) -> bool:
        """
        Check if GitHub API is accessible.

        Returns:
            bool: True if API is accessible
        """
        try:
            await self._make_request("user" if self.token else "rate_limit")
            return True
        except Exception as e:
            logger.warning("GitHub API health check failed", error=str(e))
            return False
