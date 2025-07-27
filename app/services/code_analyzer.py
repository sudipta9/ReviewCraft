"""
Code Analyzer Service

This module provides comprehensive code analysis capabilities by orchestrating
different analysis tools and generating structured results.

Features:
- File-level analysis coordination
- Integration with AI agent
- Result aggregation and formatting
- Database model creation
"""

import asyncio
from typing import Any, Dict, List

from structlog import get_logger

from app.models import AnalysisStatus, FileAnalysis, Issue, IssueType, IssueSeverity
from app.services.ai_agent import AIAgent

logger = get_logger(__name__)


class CodeAnalyzer:
    """
    Main code analysis orchestrator.

    This service coordinates different analysis tools and aggregates
    results into structured database models.
    """

    def __init__(self):
        """Initialize code analyzer."""
        self.ai_agent = AIAgent()
        logger.info("Code analyzer initialized")

    async def analyze_file(
        self,
        file_data: Dict[str, Any],
        pr_context: Dict[str, Any],
        ai_agent: AIAgent,
    ) -> FileAnalysis:
        """
        Analyze a single file from a pull request.

        Args:
            file_data: File change data from GitHub
            pr_context: Pull request context
            ai_agent: AI agent instance

        Returns:
            FileAnalysis: Analysis results
        """
        filename = file_data.get("filename", "unknown")

        logger.info("Analyzing file", filename=filename)

        # Extract file content and metadata
        file_content = file_data.get("patch", "")
        file_path = filename
        additions = file_data.get("additions", 0)
        deletions = file_data.get("deletions", 0)

        # If we have the full file content, use it; otherwise use patch
        if "content" in file_data:
            analysis_content = file_data["content"]
        else:
            # For patch analysis, we'll work with the diff
            analysis_content = file_content

        # Start analysis
        analysis_results = await self._perform_comprehensive_analysis(
            content=analysis_content,
            file_path=file_path,
            file_metadata=file_data,
            pr_context=pr_context,
            ai_agent=ai_agent,
        )

        # Create FileAnalysis model
        file_analysis = FileAnalysis(
            file_path=file_path,
            file_name=filename.split("/")[-1],
            file_extension=filename.split(".")[-1] if "." in filename else None,
            file_type=analysis_results["language"],
            analysis_status=AnalysisStatus.COMPLETED,
            lines_total=analysis_results["metrics"]["total_lines"],
            lines_analyzed=analysis_results["metrics"]["code_lines"],
            lines_added=additions,
            lines_removed=deletions,
            complexity_score=float(analysis_results["complexity_score"]),
            maintainability_index=float(analysis_results["maintainability_score"]),
            issues_count=len(analysis_results["issues"]),
            critical_issues_count=len(
                [
                    issue
                    for issue in analysis_results["issues"]
                    if issue.get("severity")
                    in [
                        "critical",
                        "high",
                    ]  # Include both critical and high as critical
                ]
            ),
            ai_recommendations=analysis_results["suggestions"],
            diff_content=file_content,
            analysis_tools_used=["ai_agent", "code_analyzer"],
        )

        # Create Issue models
        file_analysis.issues = []
        for issue_data in analysis_results["issues"]:
            # Map issue type to our enum
            issue_type_str = issue_data.get("type", "bug")
            if issue_type_str in [e.value for e in IssueType]:
                issue_type = IssueType(issue_type_str)
            else:
                # Default mapping for common types
                type_mapping = {
                    "unknown": IssueType.BUG,
                    "error": IssueType.BUG,
                    "warning": IssueType.BEST_PRACTICE,
                    "info": IssueType.STYLE,
                    "quality": IssueType.MAINTAINABILITY,
                }
                issue_type = type_mapping.get(issue_type_str, IssueType.BUG)

            # Map severity to our enum
            severity_str = issue_data.get("severity", "low")
            if severity_str in [e.value for e in IssueSeverity]:
                severity = IssueSeverity(severity_str)
            else:
                # Default mapping for common severities
                severity_mapping = {
                    "error": IssueSeverity.HIGH,
                    "warning": IssueSeverity.MEDIUM,
                    "info": IssueSeverity.LOW,
                }
                severity = severity_mapping.get(severity_str, IssueSeverity.LOW)

            issue = Issue(
                issue_type=issue_type,
                severity=severity,
                title=issue_data.get(
                    "title", issue_data.get("message", "Unknown issue")
                ),
                description=issue_data.get(
                    "message", issue_data.get("description", "")
                ),
                line_number=issue_data.get("line", 0),
                column_number=issue_data.get("column", 0),
                rule_id=issue_data.get("rule_id", ""),
                suggestion=issue_data.get("suggestion", ""),
                confidence=(
                    float(issue_data.get("confidence", 0.5))
                    if isinstance(issue_data.get("confidence"), (int, float, str))
                    else 0.5
                ),
                tags=issue_data.get("tags", []),
                references=issue_data.get("references", []),
            )
            file_analysis.issues.append(issue)

        logger.info(
            "File analysis completed",
            filename=filename,
            language=analysis_results["language"],
            issues_count=len(analysis_results["issues"]),
            quality_score=analysis_results["quality_score"],
        )

        return file_analysis

    async def _perform_comprehensive_analysis(
        self,
        content: str,
        file_path: str,
        file_metadata: Dict[str, Any],
        pr_context: Dict[str, Any],
        ai_agent: AIAgent,
    ) -> Dict[str, Any]:
        """
        Perform comprehensive analysis of file content.

        Args:
            content: File content to analyze
            file_path: Path to the file
            file_metadata: GitHub file metadata
            pr_context: Pull request context
            ai_agent: AI agent instance

        Returns:
            Dict: Comprehensive analysis results
        """
        logger.info("Performing comprehensive analysis", file_path=file_path)

        # Run different analysis types in parallel
        tasks = [
            ai_agent.analyze_code_quality(content, file_path),
            ai_agent.analyze_security(content, file_path),
            ai_agent.generate_suggestions(content, file_path),
        ]

        quality_results, security_issues, suggestions = await asyncio.gather(*tasks)

        # Aggregate all issues
        all_issues = []

        # Add quality issues
        if "issues" in quality_results:
            all_issues.extend(quality_results["issues"])

        # Add security issues
        all_issues.extend(security_issues)

        # Calculate scores
        complexity_score = quality_results.get("complexity_score", 5)
        maintainability_score = quality_results.get("maintainability_score", 75)

        # Calculate quality score based on issues and metrics
        quality_score = self._calculate_quality_score(
            quality_results, all_issues, maintainability_score
        )

        # Calculate security score
        security_score = self._calculate_security_score(security_issues)

        analysis_results = {
            "language": quality_results.get("language", "unknown"),
            "complexity_score": complexity_score,
            "quality_score": quality_score,
            "security_score": security_score,
            "maintainability_score": maintainability_score,
            "issues": all_issues,
            "suggestions": suggestions,
            "metrics": {
                "total_lines": quality_results.get("total_lines", 0),
                "code_lines": quality_results.get("code_lines", 0),
                "duplication_score": quality_results.get("duplication_score", 0),
            },
        }

        logger.info(
            "Comprehensive analysis completed",
            file_path=file_path,
            total_issues=len(all_issues),
            quality_score=quality_score,
            security_score=security_score,
        )

        return analysis_results

    def _calculate_quality_score(
        self,
        quality_results: Dict[str, Any],
        issues: List[Dict[str, Any]],
        maintainability_score: int,
    ) -> int:
        """
        Calculate overall quality score.

        Args:
            quality_results: Quality analysis results
            issues: List of all issues found
            maintainability_score: Maintainability score

        Returns:
            int: Quality score (0-100)
        """
        base_score = maintainability_score

        # Penalize based on issues
        critical_issues = len(
            [i for i in issues if i.get("severity") in ["critical", "high"]]
        )
        high_issues = len([i for i in issues if i.get("severity") == "high"])
        medium_issues = len([i for i in issues if i.get("severity") == "medium"])

        # Apply penalties
        score = base_score
        score -= critical_issues * 20
        score -= high_issues * 10
        score -= medium_issues * 5

        # Factor in complexity
        complexity = quality_results.get("complexity_score", 5)
        if complexity > 15:
            score -= (complexity - 15) * 2

        # Factor in duplication
        duplication = quality_results.get("duplication_score", 0)
        score -= int(duplication * 30)

        return max(min(score, 100), 0)

    def _calculate_security_score(self, security_issues: List[Dict[str, Any]]) -> int:
        """
        Calculate security score.

        Args:
            security_issues: List of security issues

        Returns:
            int: Security score (0-100)
        """
        if not security_issues:
            return 100

        score = 100

        critical_security = len(
            [i for i in security_issues if i.get("severity") in ["critical", "high"]]
        )
        high_security = len([i for i in security_issues if i.get("severity") == "high"])
        medium_security = len(
            [i for i in security_issues if i.get("severity") == "medium"]
        )

        # Heavy penalties for security issues
        score -= critical_security * 40
        score -= high_security * 25
        score -= medium_security * 10

        return max(score, 0)

    def _calculate_content_hash(self, content: str) -> str:
        """
        Calculate hash of file content for change detection.

        Args:
            content: File content

        Returns:
            str: Content hash
        """
        import hashlib

        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    async def analyze_diff_impact(
        self,
        file_data: Dict[str, Any],
        pr_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Analyze the impact of changes in a diff.

        Args:
            file_data: File change data
            pr_context: Pull request context

        Returns:
            Dict: Impact analysis results
        """
        patch = file_data.get("patch", "")
        filename = file_data.get("filename", "")

        logger.info("Analyzing diff impact", filename=filename)

        if not patch:
            return {
                "impact_score": 0,
                "risk_level": "low",
                "change_type": "no_changes",
                "affected_functions": [],
            }

        # Analyze patch content
        added_lines = []
        removed_lines = []
        modified_functions = set()

        lines = patch.split("\n")
        for line in lines:
            if line.startswith("+") and not line.startswith("+++"):
                added_lines.append(line[1:])
                # Simple function detection
                if "def " in line or "function " in line or "class " in line:
                    modified_functions.add(self._extract_function_name(line))
            elif line.startswith("-") and not line.startswith("---"):
                removed_lines.append(line[1:])
                if "def " in line or "function " in line or "class " in line:
                    modified_functions.add(self._extract_function_name(line))

        # Calculate impact score
        impact_score = self._calculate_impact_score(
            len(added_lines), len(removed_lines), len(modified_functions), file_data
        )

        # Determine risk level
        risk_level = self._determine_risk_level(impact_score, file_data)

        # Determine change type
        change_type = self._determine_change_type(file_data)

        impact_analysis = {
            "impact_score": impact_score,
            "risk_level": risk_level,
            "change_type": change_type,
            "affected_functions": list(modified_functions),
            "lines_added": len(added_lines),
            "lines_removed": len(removed_lines),
            "net_lines": len(added_lines) - len(removed_lines),
        }

        logger.info(
            "Diff impact analysis completed",
            filename=filename,
            impact_score=impact_score,
            risk_level=risk_level,
            affected_functions=len(modified_functions),
        )

        return impact_analysis

    def _extract_function_name(self, line: str) -> str:
        """Extract function name from code line."""
        import re

        # Python function
        python_match = re.search(r"def\s+(\w+)", line)
        if python_match:
            return python_match.group(1)

        # JavaScript function
        js_match = re.search(r"function\s+(\w+)", line)
        if js_match:
            return js_match.group(1)

        # Class definition
        class_match = re.search(r"class\s+(\w+)", line)
        if class_match:
            return class_match.group(1)

        return "unknown"

    def _calculate_impact_score(
        self,
        added_lines: int,
        removed_lines: int,
        modified_functions: int,
        file_data: Dict[str, Any],
    ) -> int:
        """Calculate impact score based on changes."""
        # Base score from line changes
        score = (added_lines + removed_lines) * 2

        # Add weight for modified functions
        score += modified_functions * 10

        # Add weight for file type
        filename = file_data.get("filename", "")
        if any(filename.endswith(ext) for ext in [".py", ".js", ".ts", ".java"]):
            score *= 1.2  # Source files have higher impact
        elif any(filename.endswith(ext) for ext in [".md", ".txt", ".json"]):
            score *= 0.5  # Documentation/config files have lower impact

        return min(int(score), 100)

    def _determine_risk_level(
        self, impact_score: int, file_data: Dict[str, Any]
    ) -> str:
        """Determine risk level based on impact score and file characteristics."""
        filename = file_data.get("filename", "")
        status = file_data.get("status", "modified")

        # Base risk from impact score
        if impact_score >= 70:
            base_risk = "high"
        elif impact_score >= 35:
            base_risk = "medium"
        else:
            base_risk = "low"

        # Adjust based on file status
        if status == "added":
            # New files are generally lower risk unless they're large
            if impact_score < 50:
                return "low"
        elif status == "removed":
            # Deleted files can be high risk
            return "medium" if base_risk == "low" else "high"

        # Adjust based on file type
        if any(keyword in filename.lower() for keyword in ["test", "spec", "mock"]):
            # Test files are lower risk
            return "low" if base_risk != "high" else "medium"
        elif any(
            keyword in filename.lower() for keyword in ["config", "setting", "env"]
        ):
            # Config files can be high risk even with small changes
            return "high" if base_risk != "low" else "medium"

        return base_risk

    def _determine_change_type(self, file_data: Dict[str, Any]) -> str:
        """Determine the type of change based on file metadata."""
        status = file_data.get("status", "modified")
        additions = file_data.get("additions", 0)
        deletions = file_data.get("deletions", 0)

        if status == "added":
            return "new_file"
        elif status == "removed":
            return "deleted_file"
        elif status == "renamed":
            return "renamed_file"
        elif deletions == 0:
            return "additions_only"
        elif additions == 0:
            return "deletions_only"
        elif additions > deletions * 3:
            return "mostly_additions"
        elif deletions > additions * 3:
            return "mostly_deletions"
        else:
            return "mixed_changes"

    async def generate_file_summary(self, file_analysis: FileAnalysis) -> str:
        """
        Generate a human-readable summary of file analysis.

        Args:
            file_analysis: File analysis results

        Returns:
            str: Human-readable summary
        """
        summary_parts = []

        # Basic info
        file_type = file_analysis.file_type or "unknown"
        summary_parts.append(f"**{file_analysis.file_name}** ({file_type})")

        # Quality metrics
        if file_analysis.maintainability_index:
            summary_parts.append(
                f"Maintainability: {file_analysis.maintainability_index:.0f}/100"
            )

        # Issues
        if file_analysis.critical_issues_count > 0:
            summary_parts.append(
                f"⚠️ {file_analysis.critical_issues_count} critical issues"
            )
        elif file_analysis.issues_count > 0:
            summary_parts.append(f"{file_analysis.issues_count} issues found")
        else:
            summary_parts.append("✅ No issues found")

        # Changes
        if file_analysis.lines_added and file_analysis.lines_removed:
            summary_parts.append(
                f"+{file_analysis.lines_added}/-{file_analysis.lines_removed} lines"
            )

        return " | ".join(summary_parts)
