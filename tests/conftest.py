"""
Test configuration and fixtures for the autonomous code review system.

This module provides pytest fixtures and test utilities for testing
all components of the system.
"""

import asyncio
import os
import pytest
from typing import Dict, Any
from unittest.mock import Mock, AsyncMock
from fastapi.testclient import TestClient

# Test environment setup
os.environ.update(
    {
        "ENVIRONMENT": "testing",
        "DATABASE_URL": "postgresql://test:test@localhost/test_db",
        "REDIS_URL": "redis://localhost:6379/1",
        "OPENROUTER_API_KEY": "test-key-for-testing",
        "GITHUB_TOKEN": "test-token",
        "DEBUG": "true",
    }
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def app():
    """Create FastAPI app instance for testing."""
    from app.main import create_app

    return create_app()


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


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
        {
            "filename": "auth/views.py",
            "status": "modified",
            "additions": 15,
            "deletions": 3,
            "changes": 18,
            "patch": "@@ -5,6 +5,8 @@ from .models import User\n def login_view(request):\n     token = request.headers.get('Authorization')\n     user = User.objects.get(token=token)\n+    if not user.is_admin():\n+        raise PermissionError('Admin required')\n     return JsonResponse({'status': 'success'})",
        },
        {
            "filename": "tests/test_auth.py",
            "status": "added",
            "additions": 20,
            "deletions": 0,
            "changes": 20,
            "patch": "@@ -0,0 +1,20 @@\n+import pytest\n+from auth.models import User\n+\n+def test_user_validation():\n+    user = User(token='valid_token_123')\n+    assert user.validate_token('valid_token_123') is True\n+    assert user.validate_token('short') is False\n+\n+def test_admin_check():\n+    admin_user = User(role='admin')\n+    regular_user = User(role='user')\n+    assert admin_user.is_admin() is True\n+    assert regular_user.is_admin() is False",
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

class DataProcessor:
    def __init__(self, config):
        self.config = config
        self.api_key = "sk-1234567890abcdef"  # Hardcoded API key (security issue)
    
    def process_data(self, data):
        # This function is too long and complex
        results = []
        for entry in data:
            if entry is None:
                continue
            processed = {}
            processed["id"] = entry.get("id")
            processed["name"] = entry.get("name", "").strip()
            processed["email"] = entry.get("email", "").lower()
            # More processing logic here...
            if processed["email"]:
                results.append(processed)
        return results
"""


@pytest.fixture
def sample_javascript_code() -> str:
    """Sample JavaScript code for testing analysis."""
    return """
var userName = "john_doe";  // Should use const/let
var userEmail = "john@example.com";

function processUser(user) {
    console.log("Processing user:", user);  // Console.log in production
    
    if (user.name == userName) {  // Should use ===
        document.getElementById("user-info").innerHTML = user.bio;  // XSS vulnerability
    }
    
    return {
        name: user.name,
        email: user.email,
        processed: true
    };
}

function calculateTotal(items) {
    var total = 0;
    for (var i = 0; i < items.length; i++) {
        total += items[i].price;
    }
    return total;
}
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
            "issues": [
                {
                    "type": "style",
                    "severity": "low",
                    "line": 15,
                    "message": "Line too long",
                    "suggestion": "Break line for readability",
                }
            ],
            "maintainability_score": 75,
        }
    )

    agent.analyze_security = AsyncMock(
        return_value=[
            {
                "type": "sensitive_data",
                "severity": "critical",
                "line": 12,
                "message": "Hardcoded API key detected",
                "suggestion": "Use environment variables",
            }
        ]
    )

    agent.generate_suggestions = AsyncMock(
        return_value=[
            {
                "type": "refactoring",
                "priority": "medium",
                "message": "Consider breaking down large function",
                "suggestion": "Extract smaller functions for better maintainability",
            }
        ]
    )

    agent.generate_summary = AsyncMock(
        return_value={
            "overall_quality": "good",
            "overall_score": 78,
            "total_files_analyzed": 3,
            "total_issues": 5,
            "critical_issues": 1,
            "security_issues": 1,
            "recommendations": ["Address critical security issues"],
            "analysis_timestamp": "2024-01-15T12:00:00.000000",
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
    from unittest.mock import Mock

    # Create mock settings structure
    settings = Mock()
    settings.app_name = "Test Code Review Agent"
    settings.environment = "testing"
    settings.debug = True
    settings.api_host = "127.0.0.1"
    settings.api_port = 8000

    # Mock nested settings
    settings.database = Mock()
    settings.database.url = "postgresql://test:test@localhost/test_db"

    settings.ai = Mock()
    settings.ai.openrouter_api_key = "test-key"
    settings.ai.openrouter_model = "qwen/qwen3-coder:free"

    settings.github = Mock()
    settings.github.token = "test-token"

    settings.celery = Mock()
    settings.celery.broker_url = "amqp://test:test@localhost:5672//"

    settings.redis = Mock()
    settings.redis.url = "redis://localhost:6379/1"

    return settings


@pytest.fixture
async def async_db_session():
    """Create async database session for testing."""
    # Note: This would need proper test database setup in real implementation
    from unittest.mock import AsyncMock

    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


# Test markers
pytest_mark_unit = pytest.mark.unit
pytest_mark_integration = pytest.mark.integration
pytest_mark_slow = pytest.mark.slow
