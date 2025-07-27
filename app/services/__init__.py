"""
Services Package

This package contains service classes for external integrations and business logic.

Services:
- GitHubClient: GitHub API integration
- AIAgent: AI-powered code analysis
- CodeAnalyzer: Code quality analysis
- LLMClient: Large Language Model integration (OpenRouter)
- CodeEmbeddingsService: Semantic code analysis using embeddings
"""

from .github_client import GitHubClient
from .ai_agent import AIAgent
from .code_analyzer import CodeAnalyzer
from .llm_client import LLMClient
from .code_embeddings import CodeEmbeddingsService

__all__ = [
    "GitHubClient",
    "AIAgent",
    "CodeAnalyzer",
    "LLMClient",
    "CodeEmbeddingsService",
]
