"""
Test configuration and fixtures for the autonomous code review system.

This module provides pytest fixtures and test utilities for testing
all components of the system with proper async support.
"""

import asyncio
import os
import pytest
import pytest_asyncio
from typing import Dict, Any, AsyncGenerator
from unittest.mock import Mock, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import create_app
from app.database import Base

# Test environment setup - MUST be done before importing app modules
os.environ.update(
    {
        "ENVIRONMENT": "development",  # Use development to enable OpenAPI docs
        "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "REDIS_URL": "redis://localhost:6379/1",
        "OPENROUTER_API_KEY": "test-key-for-testing",
        "GITHUB_TOKEN": "test-token",
        "DEBUG": "true",
        "LOG_LEVEL": "ERROR",
    }
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        echo=False,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def app():
    """Create FastAPI app instance for testing."""
    # Import here to avoid circular dependencies
    from app.database import DatabaseManager, Base

    # Import models to ensure they are registered with SQLAlchemy
    from app.models import Task, PRAnalysis, FileAnalysis, Issue

    # Create the app
    app = create_app()

    # Get the database manager and create tables
    db_manager = DatabaseManager()
    async with db_manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield app

    # Cleanup - drop tables
    async with db_manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def client(app):
    """Create test client."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def mock_celery_task():
    """Mock Celery task for testing."""
    mock_task = Mock()
    mock_task.id = "test-celery-task-123"
    mock_task.state = "PENDING"
    mock_task.info = None
    return mock_task


@pytest.fixture
def mock_github_pr_data() -> Dict[str, Any]:
    """Mock GitHub PR data for testing."""
    return {
        "id": 123456789,
        "number": 42,
        "title": "Fix authentication bug",
        "body": "This PR fixes the authentication issue by updating the token validation.",
        "state": "open",
        "created_at": "2024-01-15T10:30:00Z",
        "updated_at": "2024-01-15T11:00:00Z",
        "user": {"login": "test-user", "id": 987654321},
        "head": {"sha": "abc123def456", "ref": "feature/auth-fix"},
        "base": {"sha": "def456ghi789", "ref": "main"},
        "changed_files": 3,
        "additions": 45,
        "deletions": 12,
        "commits": 2,
        "_metadata": {
            "owner": "test-owner",
            "repo": "test-repo",
            "fetched_at": 1234567890.0,
        },
    }


@pytest.fixture
def mock_github_files_data() -> list:
    """Mock GitHub files data for testing."""
    return [
        {
            "filename": "auth/models.py",
            "status": "modified",
            "additions": 25,
            "deletions": 5,
            "changes": 30,
            "patch": "@@ -10,7 +10,7 @@ class User:\n-    def validate_token(self, token):\n+    def validate_token(self, token: str) -> bool:\n         return token and len(token) > 10\n\n+    def is_admin(self) -> bool:\n+        return self.role == 'admin'",
        },
    ]


@pytest.fixture
def sample_python_code() -> str:
    """Sample Python code for testing analysis."""
    return """
def calculate_score(items):
    total = 0
    for item in items:
        if item.type == "premium":
            total += item.value * 1.5
        else:
            total += item.value
    return total
"""


@pytest.fixture
def mock_ai_agent():
    """Mock AI agent for testing."""
    agent = Mock()
    agent.analyze_code_quality = AsyncMock(
        return_value={
            "total_lines": 50,
            "code_lines": 40,
            "complexity_score": 7,
            "duplication_score": 0.1,
            "language": "python",
            "issues": [],
            "maintainability_score": 75,
        }
    )
    return agent


@pytest.fixture
def mock_github_client():
    """Mock GitHub client for testing."""
    client = Mock()
    client.get_pull_request = AsyncMock()
    client.get_pr_files = AsyncMock()
    client.get_file_content = AsyncMock(return_value="sample file content")
    client.health_check = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    mock_settings = Mock()
    mock_settings.app_name = "Test Code Review Agent"
    mock_settings.environment = "testing"
    mock_settings.debug = True
    mock_settings.is_development = True

    # Mock nested configs
    mock_settings.database = Mock()
    mock_settings.database.url = "sqlite+aiosqlite:///:memory:"

    mock_settings.ai = Mock()
    mock_settings.ai.openrouter_api_key = "test-key"

    mock_settings.github = Mock()
    mock_settings.github.token = "test-token"

    return mock_settings
