"""
AI Agent for Code Analysis

This module provides an AI-powered agent for analyzing code changes,
generating insights, and providing structured feedback on pull requests.

Features:
- Code quality assessment using LLM
- Security vulnerability detection
- Best practices recommendations
- Semantic code analysis using embeddings
- Contextual analysis based on programming language
- Structured feedback generation
"""

from datetime import datetime, timezone
from typing import Any, Dict, List

from structlog import get_logger
from whats_that_code.election import guess_language_all_methods

from app.config import get_settings
from app.services.code_embeddings import CodeEmbeddingsService
from app.services.llm_client import LLMClient

logger = get_logger(__name__)


class AIAgent:
    """
    AI-powered code analysis agent.

    This agent uses various AI techniques to analyze code changes
    and generate structured feedback for pull requests.
    """

    def __init__(self):
        """Initialize AI agent with configuration."""
        self.settings = get_settings()
        self.analysis_rules = self._load_analysis_rules()

        # Initialize LLM client and embeddings service
        self.llm_client = LLMClient()
        self.embeddings_service = CodeEmbeddingsService()

        logger.info(
            "AI Agent initialized",
            rules_count=len(self.analysis_rules),
            llm_provider=self.llm_client._get_provider(),
            embeddings_model=self.embeddings_service.model_name,
        )

    def _load_analysis_rules(self) -> Dict[str, Any]:
        """
        Load analysis rules and patterns.

        Returns:
            Dict: Analysis rules configuration
        """
        return {
            "code_quality": {
                "max_function_length": 50,
                "max_file_length": 500,
                "complexity_threshold": 10,
                "duplication_threshold": 0.3,
            },
            "security": {
                "sql_injection_patterns": [
                    r"(?i)SELECT.*FROM.*WHERE.*=.*\+",
                    r"(?i)INSERT.*VALUES.*\+",
                    r"(?i)UPDATE.*SET.*=.*\+",
                ],
                "xss_patterns": [
                    r"innerHTML\s*=",
                    r"document\.write\(",
                    r"eval\(",
                ],
                "sensitive_data_patterns": [
                    r"(?i)(password|secret|key|token)\s*=\s*['\"][^'\"]+['\"]",
                    r"(?i)api_key\s*=",
                ],
            },
            "best_practices": {
                "python": {
                    "required_imports": ["typing", "logging"],
                    "naming_conventions": r"^[a-z_][a-z0-9_]*$",
                    "max_line_length": 88,
                },
                "javascript": {
                    "required_patterns": ["const", "let"],
                    "forbidden_patterns": ["var"],
                    "max_line_length": 100,
                },
                "typescript": {
                    "required_patterns": ["interface", "type"],
                    "strict_mode": True,
                    "max_line_length": 100,
                },
            },
        }

    async def analyze_code_quality(
        self, file_content: str, file_path: str
    ) -> Dict[str, Any]:
        """
        Analyze code quality metrics using LLM and embeddings.

        Args:
            file_content: File content to analyze
            file_path: Path to the file

        Returns:
            Dict: Quality analysis results
        """
        logger.info("Analyzing code quality", file_path=file_path)

        # Detect language
        language = self._detect_language(file_path)

        # Use LLM for comprehensive quality analysis
        quality_results = await self.llm_client.analyze_code_quality(
            file_content, file_path, language
        )

        # Enhance with embeddings-based analysis
        similarity_metrics = self.embeddings_service.analyze_code_similarity_metrics(
            file_content
        )

        # Combine results
        quality_results.update(
            {
                "semantic_duplicates": similarity_metrics.get("duplicates_found", 0),
                "duplication_score": similarity_metrics.get("duplication_score", 0.0),
                "code_blocks_analyzed": similarity_metrics.get("total_blocks", 0),
            }
        )

        logger.info(
            "Code quality analysis complete",
            file_path=file_path,
            language=language,
            complexity=quality_results.get("complexity_score", 0),
            maintainability=quality_results.get("maintainability_score", 0),
            semantic_duplicates=similarity_metrics.get("duplicates_found", 0),
        )

        return quality_results

    async def analyze_security(
        self, file_content: str, file_path: str
    ) -> List[Dict[str, Any]]:
        """
        Analyze code for security vulnerabilities using LLM.

        Args:
            file_content: File content to analyze
            file_path: Path to the file

        Returns:
            List[Dict]: Security issues found
        """
        logger.info("Analyzing security", file_path=file_path)

        # Detect language
        language = self._detect_language(file_path)

        # Use LLM for comprehensive security analysis
        security_issues = await self.llm_client.analyze_security(
            file_content, file_path, language
        )

        logger.info(
            "Security analysis complete",
            file_path=file_path,
            issues_found=len(security_issues),
        )

        return security_issues

    async def generate_suggestions(
        self, file_content: str, file_path: str
    ) -> List[Dict[str, Any]]:
        """
        Generate improvement suggestions using LLM.

        Args:
            file_content: File content to analyze
            file_path: Path to the file

        Returns:
            List[Dict]: Improvement suggestions
        """
        logger.info("Generating suggestions", file_path=file_path)

        # Detect language
        language = self._detect_language(file_path)

        # Use LLM for comprehensive suggestions
        suggestions = await self.llm_client.generate_suggestions(
            file_content, file_path, language
        )

        logger.info(
            "Suggestions generated", file_path=file_path, count=len(suggestions)
        )

        return suggestions

    async def generate_summary(
        self, pr_data: Dict[str, Any], file_analyses: List[Any], total_issues: int
    ) -> Dict[str, Any]:
        """
        Generate overall analysis summary.

        Args:
            pr_data: Pull request data
            file_analyses: List of file analysis results
            total_issues: Total number of issues found

        Returns:
            Dict: Analysis summary
        """
        logger.info(
            "Generating summary",
            total_files=len(file_analyses),
            total_issues=total_issues,
        )

        # Calculate overall scores
        quality_scores = []
        security_issues_count = 0
        critical_issues_count = 0

        for analysis in file_analyses:
            if hasattr(analysis, "quality_score"):
                quality_scores.append(analysis.quality_score)

            if hasattr(analysis, "issues"):
                for issue in analysis.issues:
                    if getattr(issue, "severity", "") == "critical":
                        critical_issues_count += 1
                    if getattr(issue, "type", "").startswith("security"):
                        security_issues_count += 1

        avg_quality = (
            sum(quality_scores) / len(quality_scores) if quality_scores else 75
        )

        # Generate recommendations
        recommendations = []

        if critical_issues_count > 0:
            recommendations.append(
                f"Address {critical_issues_count} critical security issues immediately"
            )

        if avg_quality < 70:
            recommendations.append("Consider refactoring to improve code quality")

        if len(file_analyses) > 20:
            recommendations.append("Large PR - consider breaking into smaller changes")

        if not recommendations:
            recommendations.append(
                "Code looks good! Consider adding tests if not present"
            )

        # Overall assessment
        if critical_issues_count > 0:
            overall_quality = "needs_work"
        elif avg_quality >= 85:
            overall_quality = "excellent"
        elif avg_quality >= 75:
            overall_quality = "good"
        else:
            overall_quality = "fair"

        summary = {
            "overall_quality": overall_quality,
            "overall_score": int(avg_quality),
            "total_files_analyzed": len(file_analyses),
            "total_issues": total_issues,
            "critical_issues": critical_issues_count,
            "security_issues": security_issues_count,
            "recommendations": recommendations,
            "analysis_timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "pr_metadata": {
                "title": pr_data.get("title", ""),
                "author": pr_data.get("user", {}).get("login", ""),
                "files_changed": pr_data.get("changed_files", 0),
            },
        }

        logger.info(
            "Summary generated",
            overall_quality=overall_quality,
            overall_score=avg_quality,
            critical_issues=critical_issues_count,
        )

        return summary

    # Helper methods

    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension."""
        language = "unknown"
        try:
            result = guess_language_all_methods(file_name=file_path, code="")
            language = result if result else "unknown"
        except Exception as e:
            logger.error(f"Error detecting language for {file_path}: {e}")
        return language

    async def _calculate_complexity(self, content: str, file_path: str) -> int:
        """Calculate cyclomatic complexity (simplified)."""
        # Simplified complexity calculation
        complexity_keywords = [
            "if",
            "else",
            "elif",
            "for",
            "while",
            "try",
            "except",
            "finally",
        ]

        complexity = 1  # Base complexity
        lines = content.lower().split("\n")

        for line in lines:
            line = line.strip()
            for keyword in complexity_keywords:
                if keyword in line:
                    complexity += 1

        return min(complexity, 50)  # Cap at 50

    async def _check_duplication(self, content: str) -> float:
        """Check for code duplication (simplified)."""
        lines = [line.strip() for line in content.split("\n") if line.strip()]

        if len(lines) < 10:
            return 0.0

        # Simple duplicate line detection
        line_counts = {}
        for line in lines:
            if len(line) > 10:  # Only check meaningful lines
                line_counts[line] = line_counts.get(line, 0) + 1

        duplicated_lines = sum(count - 1 for count in line_counts.values() if count > 1)
        duplication_ratio = duplicated_lines / len(lines) if lines else 0

        return min(duplication_ratio, 1.0)

    def _calculate_maintainability_score(
        self, lines: int, complexity: int, duplication: float
    ) -> int:
        """Calculate maintainability score."""
        # Simple scoring algorithm
        score = 100

        # Penalize long files
        if lines > 300:
            score -= min(20, (lines - 300) // 50)

        # Penalize high complexity
        if complexity > 10:
            score -= min(30, (complexity - 10) * 2)

        # Penalize duplication
        score -= int(duplication * 40)

        return max(score, 0)

    async def _analyze_language_specific(
        self, content: str, language: str
    ) -> List[Dict[str, Any]]:
        """Perform language-specific analysis."""
        issues = []

        if language == "python":
            issues.extend(await self._analyze_python_specific(content))
        elif language in ["javascript", "typescript"]:
            issues.extend(await self._analyze_javascript_specific(content))

        return issues

    async def _analyze_python_specific(self, content: str) -> List[Dict[str, Any]]:
        """Python-specific analysis."""
        import re

        issues = []
        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            # Check for long lines
            if len(line) > 88:
                issues.append(
                    {
                        "type": "style",
                        "severity": "low",
                        "line": i,
                        "message": f"Line too long ({len(line)} > 88 characters)",
                        "suggestion": "Break long lines for better readability",
                    }
                )

            # Check for missing type hints (simplified)
            if re.match(r"^\s*def\s+\w+\s*\([^)]*\)\s*:", line):
                if "->" not in line:
                    issues.append(
                        {
                            "type": "typing",
                            "severity": "low",
                            "line": i,
                            "message": "Missing return type annotation",
                            "suggestion": "Add return type annotation for better code documentation",
                        }
                    )

        return issues

    async def _analyze_javascript_specific(self, content: str) -> List[Dict[str, Any]]:
        """JavaScript/TypeScript-specific analysis."""
        import re

        issues = []
        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            # Check for var usage (should use let/const)
            if re.search(r"\bvar\s+", line):
                issues.append(
                    {
                        "type": "style",
                        "severity": "medium",
                        "line": i,
                        "message": "Use 'let' or 'const' instead of 'var'",
                        "suggestion": "Replace 'var' with 'let' or 'const' for better scoping",
                    }
                )

            # Check for console.log (shouldn't be in production)
            if "console.log" in line:
                issues.append(
                    {
                        "type": "style",
                        "severity": "low",
                        "line": i,
                        "message": "Remove console.log statements",
                        "suggestion": "Use proper logging library instead of console.log",
                    }
                )

        return issues

    async def _python_suggestions(self, content: str) -> List[Dict[str, Any]]:
        """Generate Python-specific suggestions."""
        suggestions = []

        if "import *" in content:
            suggestions.append(
                {
                    "type": "import",
                    "priority": "medium",
                    "message": "Avoid wildcard imports",
                    "suggestion": "Use explicit imports for better code clarity",
                }
            )

        if "except:" in content and "except Exception:" not in content:
            suggestions.append(
                {
                    "type": "exception_handling",
                    "priority": "high",
                    "message": "Use specific exception types",
                    "suggestion": "Catch specific exceptions instead of bare except clauses",
                }
            )

        return suggestions

    async def _javascript_suggestions(self, content: str) -> List[Dict[str, Any]]:
        """Generate JavaScript-specific suggestions."""
        suggestions = []

        if "==" in content and "===" not in content:
            suggestions.append(
                {
                    "type": "comparison",
                    "priority": "medium",
                    "message": "Use strict equality",
                    "suggestion": "Use '===' instead of '==' for strict comparison",
                }
            )

        return suggestions

    async def _general_suggestions(
        self, content: str, file_path: str
    ) -> List[Dict[str, Any]]:
        """Generate general improvement suggestions."""
        suggestions = []

        # Check for very long functions (simplified)
        function_lengths = self._estimate_function_lengths(content)
        for func_name, length in function_lengths.items():
            if length > 50:
                suggestions.append(
                    {
                        "type": "refactoring",
                        "priority": "medium",
                        "message": f"Function '{func_name}' is too long ({length} lines)",
                        "suggestion": "Consider breaking large functions into smaller, focused functions",
                    }
                )

        return suggestions

    def _estimate_function_lengths(self, content: str) -> Dict[str, int]:
        """Estimate function lengths (simplified)."""
        import re

        function_lengths = {}
        content_lines = content.split("\n")

        current_function = None
        function_start = 0
        indent_level = 0

        for i, line in enumerate(content_lines):
            # Simple function detection (works for Python, adjust for other languages)
            if re.match(r"^\s*def\s+(\w+)", line):
                if current_function:
                    function_lengths[current_function] = i - function_start

                match = re.match(r"^\s*def\s+(\w+)", line)
                current_function = match.group(1) if match else "unknown"
                function_start = i
                indent_level = len(line) - len(line.lstrip())
            elif (
                current_function
                and line.strip()
                and len(line) - len(line.lstrip()) <= indent_level
            ):
                # End of current function
                function_lengths[current_function] = i - function_start
                current_function = None

        # Handle last function
        if current_function:
            function_lengths[current_function] = len(content_lines) - function_start

        return function_lengths
