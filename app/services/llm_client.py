"""
OpenRouter LLM client for code analysis.

This module provides a unified interface for interacting with OpenRouter
to perform AI-powered code analysis including quality assessment,
security vulnerability detection, and improvement suggestions.
"""

import json
import time
from typing import Dict, Any, List, Optional

from openai import OpenAI
from structlog import get_logger

from ..config import get_settings


logger = get_logger()


def log_ai_request(
    operation: str,
    model: str,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    duration_seconds: Optional[float] = None,
):
    """Simple logging function for AI requests."""
    logger.info(
        "AI request completed",
        operation=operation,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        duration_seconds=duration_seconds,
    )


class LLMClient:
    """
    OpenRouter LLM client for code analysis.

    Provides interface for AI model interactions using OpenRouter
    with automatic fallback to mock responses if unavailable.
    """

    def __init__(self):
        """Initialize LLM client with OpenRouter configuration."""
        self.settings = get_settings()
        self.ai_config = self.settings.ai
        self._client = None
        self._initialize_client()

        logger.info(
            "LLM Client initialized",
            provider="openrouter",
            model=self.ai_config.openrouter_model,
        )

    def _initialize_client(self):
        """Initialize the OpenRouter client."""
        if self.ai_config.openrouter_api_key:
            # OpenRouter client (OpenAI-compatible)
            self._client = OpenAI(
                base_url=self.ai_config.openrouter_base_url,
                api_key=self.ai_config.openrouter_api_key,
            )
            logger.info(
                "Using OpenRouter client", model=self.ai_config.openrouter_model
            )
        else:
            logger.warning("No OpenRouter API key found, using mock mode")
            self._client = None

    def _get_provider(self) -> str:
        """Get the current provider name."""
        return "openrouter"

    def _get_model(self) -> str:
        """Get the current model name."""
        return self.ai_config.openrouter_model

    async def analyze_code_quality(
        self, file_content: str, file_path: str, language: str = "unknown"
    ) -> Dict[str, Any]:
        """
        Analyze code quality using LLM.

        Args:
            file_content: The code content to analyze
            file_path: Path to the file being analyzed
            language: Programming language of the code

        Returns:
            Dictionary containing code quality analysis
        """
        if not self._client:
            return self._mock_quality_analysis()

        prompt = self._build_quality_analysis_prompt(file_content, file_path, language)

        try:
            start_time = time.time()

            response = self._client.chat.completions.create(
                model=self._get_model(),
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert code reviewer. Analyze the provided code and return detailed quality metrics in JSON format.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=self.ai_config.temperature,
                max_tokens=self.ai_config.max_tokens,
                extra_headers=self._get_extra_headers(),
            )

            duration = time.time() - start_time

            # Log the request
            log_ai_request(
                operation="analyze_code_quality",
                model=self._get_model(),
                prompt_tokens=response.usage.prompt_tokens if response.usage else None,
                completion_tokens=(
                    response.usage.completion_tokens if response.usage else None
                ),
                duration_seconds=duration,
            )

            content = response.choices[0].message.content
            if content:
                # Try to parse JSON response
                try:
                    result = json.loads(content)
                    return result
                except json.JSONDecodeError:
                    # If not JSON, wrap in structure
                    return {
                        "score": 7.5,
                        "issues": [],
                        "suggestions": [content],
                        "metrics": {
                            "maintainability": 8,
                            "readability": 7,
                            "complexity": 6,
                        },
                    }

        except Exception as e:
            logger.error(f"Error in code quality analysis: {e}")

        return self._mock_quality_analysis()

    async def analyze_security(
        self, file_content: str, file_path: str, language: str = "unknown"
    ) -> List[Dict[str, Any]]:
        """
        Analyze code for security vulnerabilities.

        Args:
            file_content: The code content to analyze
            file_path: Path to the file being analyzed
            language: Programming language of the code

        Returns:
            List of security issues found
        """
        if not self._client:
            return self._mock_security_analysis()

        prompt = self._build_security_analysis_prompt(file_content, file_path, language)

        try:
            start_time = time.time()

            response = self._client.chat.completions.create(
                model=self._get_model(),
                messages=[
                    {
                        "role": "system",
                        "content": "You are a security expert. Analyze the provided code for security vulnerabilities and return a JSON array of issues found.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=self.ai_config.temperature,
                max_tokens=self.ai_config.max_tokens,
                extra_headers=self._get_extra_headers(),
            )

            duration = time.time() - start_time

            # Log the request
            log_ai_request(
                operation="analyze_security",
                model=self._get_model(),
                prompt_tokens=response.usage.prompt_tokens if response.usage else None,
                completion_tokens=(
                    response.usage.completion_tokens if response.usage else None
                ),
                duration_seconds=duration,
            )

            content = response.choices[0].message.content
            if content:
                # Try to parse JSON response
                try:
                    result = json.loads(content)
                    return result if isinstance(result, list) else [result]
                except json.JSONDecodeError:
                    # If not JSON, wrap in structure
                    return [
                        {
                            "type": "info",
                            "severity": "medium",
                            "title": "Security Analysis",
                            "description": content,
                            "line": 1,
                        }
                    ]

        except Exception as e:
            logger.error(f"Error in security analysis: {e}")

        return self._mock_security_analysis()

    async def generate_suggestions(
        self, file_content: str, file_path: str, language: str = "unknown"
    ) -> List[Dict[str, Any]]:
        """
        Generate improvement suggestions for code.

        Args:
            file_content: The code content to analyze
            file_path: Path to the file being analyzed
            language: Programming language of the code

        Returns:
            List of improvement suggestions
        """
        if not self._client:
            return self._mock_suggestions()

        prompt = self._build_suggestions_prompt(file_content, file_path, language)

        try:
            start_time = time.time()

            response = self._client.chat.completions.create(
                model=self._get_model(),
                messages=[
                    {
                        "role": "system",
                        "content": "You are a senior software engineer. Provide constructive code improvement suggestions in JSON format.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=self.ai_config.temperature,
                max_tokens=self.ai_config.max_tokens,
                extra_headers=self._get_extra_headers(),
            )

            duration = time.time() - start_time

            # Log the request
            log_ai_request(
                operation="generate_suggestions",
                model=self._get_model(),
                prompt_tokens=response.usage.prompt_tokens if response.usage else None,
                completion_tokens=(
                    response.usage.completion_tokens if response.usage else None
                ),
                duration_seconds=duration,
            )

            content = response.choices[0].message.content
            if content:
                # Try to parse JSON response
                try:
                    result = json.loads(content)
                    return result if isinstance(result, list) else [result]
                except json.JSONDecodeError:
                    # If not JSON, wrap in structure
                    return [
                        {
                            "type": "improvement",
                            "priority": "medium",
                            "title": "Code Improvement",
                            "description": content,
                            "line": 1,
                        }
                    ]

        except Exception as e:
            logger.error(f"Error in generating suggestions: {e}")

        return self._mock_suggestions()

    def _get_extra_headers(self) -> Dict[str, str]:
        """Get extra headers for OpenRouter requests."""
        return {
            "HTTP-Referer": "https://potpieai.dev",
            "X-Title": "PotPie AI Code Review Agent",
        }

    def _build_quality_analysis_prompt(
        self, file_content: str, file_path: str, language: str
    ) -> str:
        """Build prompt for code quality analysis."""
        return f"""
Analyze the following {language} code for quality metrics and issues:

File: {file_path}

```{language}
{file_content}
```

Provide a detailed analysis in JSON format with these fields:
- score: Overall quality score (0-10)
- issues: Array of specific issues found
- suggestions: Array of improvement suggestions
- metrics: Object with maintainability, readability, complexity scores (0-10)

Focus on:
- Code structure and organization
- Variable and function naming
- Code complexity and maintainability
- Best practices adherence
- Documentation quality
"""

    def _build_security_analysis_prompt(
        self, file_content: str, file_path: str, language: str
    ) -> str:
        """Build prompt for security analysis."""
        return f"""
Analyze the following {language} code for security vulnerabilities:

File: {file_path}

```{language}
{file_content}
```

Return a JSON array of security issues with these fields for each issue:
- type: Type of vulnerability (e.g., "sql_injection", "xss", "hardcoded_secret")
- severity: "low", "medium", "high", or "critical"
- title: Brief title of the issue
- description: Detailed description of the vulnerability
- line: Line number where the issue occurs
- recommendation: How to fix the issue

Look for:
- SQL injection vulnerabilities
- Cross-site scripting (XSS)
- Hardcoded secrets/passwords
- Insecure data handling
- Authentication/authorization issues
- Input validation problems
"""

    def _build_suggestions_prompt(
        self, file_content: str, file_path: str, language: str
    ) -> str:
        """Build prompt for improvement suggestions."""
        return f"""
Review the following {language} code and provide improvement suggestions:

File: {file_path}

```{language}
{file_content}
```

Return a JSON array of suggestions with these fields for each suggestion:
- type: Type of improvement (e.g., "performance", "readability", "best_practice")
- priority: "low", "medium", or "high"
- title: Brief title of the suggestion
- description: Detailed description of the improvement
- line: Line number where the improvement applies
- example: Optional code example showing the improvement

Focus on:
- Performance optimizations
- Code readability improvements
- Best practice adoption
- Error handling enhancements
- Code maintainability
"""

    def _mock_quality_analysis(self) -> Dict[str, Any]:
        """Return mock quality analysis when AI is unavailable."""
        return {
            "score": 8.0,
            "issues": [
                {
                    "type": "warning",
                    "title": "Mock Analysis",
                    "description": "AI service unavailable - showing mock results",
                    "line": 1,
                }
            ],
            "suggestions": [
                {
                    "type": "info",
                    "title": "Configure AI Service",
                    "description": "Set up OpenRouter API key to enable real analysis",
                    "priority": "high",
                }
            ],
            "metrics": {"maintainability": 8, "readability": 8, "complexity": 7},
        }

    def _mock_security_analysis(self) -> List[Dict[str, Any]]:
        """Return mock security analysis when AI is unavailable."""
        return [
            {
                "type": "info",
                "severity": "low",
                "title": "Mock Security Analysis",
                "description": "AI service unavailable - configure OpenRouter API key for real security analysis",
                "line": 1,
                "recommendation": "Set up OpenRouter API key in environment variables",
            }
        ]

    def _mock_suggestions(self) -> List[Dict[str, Any]]:
        """Return mock suggestions when AI is unavailable."""
        return [
            {
                "type": "info",
                "priority": "medium",
                "title": "Configure AI Service",
                "description": "Set up OpenRouter API key to enable AI-powered code suggestions",
                "line": 1,
                "example": "export OPENROUTER_API_KEY=your_api_key_here",
            }
        ]
