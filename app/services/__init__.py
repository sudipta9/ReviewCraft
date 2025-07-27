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

from .ai_agent import AIAgent
from .code_analyzer import CodeAnalyzer
from .code_embeddings import CodeEmbeddingsService
from .github_client import GitHubClient
from .llm_client import LLMClient

__all__ = [
    "GitHubClient",
    "AIAgent",
    "CodeAnalyzer",
    "LLMClient",
    "CodeEmbeddingsService",
]
