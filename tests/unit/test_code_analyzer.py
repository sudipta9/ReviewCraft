"""
Unit tests for the Code Analyzer service.

Tests cover file analysis orchestration, quality score calculation,
and integration with AI agent functionality.
"""

import pytest
from unittest.mock import Mock, patch

from app.services.code_analyzer import CodeAnalyzer
from app.models import FileAnalysis, AnalysisStatus


class TestCodeAnalyzer:
    """Test suite for CodeAnalyzer service."""

    @pytest.fixture
    def code_analyzer(self):
        """Create code analyzer instance for testing."""
        with patch("app.services.code_analyzer.AIAgent"):
            return CodeAnalyzer()

    @pytest.mark.unit
    def test_analyzer_initialization(self, code_analyzer):
        """Test code analyzer initialization."""
        assert code_analyzer is not None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_file_analysis_success(
        self, code_analyzer, mock_github_files_data, mock_ai_agent
    ):
        """Test successful file analysis."""
        file_data = mock_github_files_data[0]  # auth/models.py
        pr_context = {"pr_number": 42, "base_branch": "main"}

        # Mock the comprehensive analysis
        with patch.object(
            code_analyzer, "_perform_comprehensive_analysis"
        ) as mock_analysis:
            mock_analysis.return_value = {
                "language": "python",
                "complexity_score": 7,
                "quality_score": 78,
                "security_score": 85,
                "maintainability_score": 75,
                "issues": [
                    {
                        "type": "style",
                        "severity": "low",
                        "message": "Line too long",
                        "line": 15,
                        "suggestion": "Break line for readability",
                    }
                ],
                "suggestions": [
                    {
                        "type": "refactoring",
                        "message": "Consider type hints",
                        "priority": "medium",
                    }
                ],
                "metrics": {
                    "total_lines": 50,
                    "code_lines": 40,
                    "duplication_score": 0.1,
                },
            }

            result = await code_analyzer.analyze_file(
                file_data, pr_context, mock_ai_agent
            )

            assert isinstance(result, FileAnalysis)
            assert result.file_path == "auth/models.py"
            assert result.file_name == "models.py"
            assert result.file_extension == "py"
            assert result.file_type == "python"
            assert result.analysis_status == AnalysisStatus.COMPLETED
            assert result.lines_added == 25
            assert result.lines_removed == 5
            assert result.complexity_score == 7
            assert result.issues_count == 1
            assert len(result.issues) == 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_comprehensive_analysis(
        self, code_analyzer, sample_python_code, mock_ai_agent
    ):
        """Test comprehensive analysis functionality."""
        file_metadata = {"filename": "test.py", "status": "modified"}
        pr_context = {"pr_number": 42}

        result = await code_analyzer._perform_comprehensive_analysis(
            content=sample_python_code,
            file_path="test.py",
            file_metadata=file_metadata,
            pr_context=pr_context,
            ai_agent=mock_ai_agent,
        )

        assert isinstance(result, dict)
        assert "language" in result
        assert "complexity_score" in result
        assert "quality_score" in result
        assert "security_score" in result
        assert "maintainability_score" in result
        assert "issues" in result
        assert "suggestions" in result
        assert "metrics" in result

    @pytest.mark.unit
    def test_quality_score_calculation(self, code_analyzer):
        """Test quality score calculation logic."""
        # Test high quality scenario
        quality_results = {
            "complexity_score": 5,
            "duplication_score": 0.1,
            "maintainability_score": 85,
        }
        issues = [
            {"severity": "low", "type": "style"},
            {"severity": "medium", "type": "logic"},
        ]
        maintainability_score = 85

        score = code_analyzer._calculate_quality_score(
            quality_results, issues, maintainability_score
        )

        assert isinstance(score, int)
        assert 0 <= score <= 100
        assert score > 70  # Should be high quality

        # Test low quality scenario
        quality_results_bad = {
            "complexity_score": 20,
            "duplication_score": 0.6,
            "maintainability_score": 30,
        }
        issues_bad = [
            {"severity": "critical", "type": "security"},
            {"severity": "high", "type": "bug"},
            {"severity": "medium", "type": "style"},
        ]

        score_bad = code_analyzer._calculate_quality_score(
            quality_results_bad, issues_bad, 30
        )

        assert score_bad < score  # Should be lower quality

    @pytest.mark.unit
    def test_security_score_calculation(self, code_analyzer):
        """Test security score calculation."""
        # Test secure code
        security_issues_none = []
        score_secure = code_analyzer._calculate_security_score(security_issues_none)
        assert score_secure == 100

        # Test code with security issues
        security_issues = [
            {"severity": "critical", "type": "sql_injection"},
            {"severity": "high", "type": "xss"},
            {"severity": "medium", "type": "sensitive_data"},
        ]
        score_insecure = code_analyzer._calculate_security_score(security_issues)
        assert score_insecure < score_secure
        assert score_insecure >= 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_diff_impact_analysis(self, code_analyzer):
        """Test diff impact analysis functionality."""
        file_data = {
            "filename": "auth/models.py",
            "status": "modified",
            "additions": 25,
            "deletions": 5,
            "patch": """@@ -10,7 +10,7 @@ class User:
-    def validate_token(self, token):
+    def validate_token(self, token: str) -> bool:
         return token and len(token) > 10

+    def is_admin(self) -> bool:
+        return self.role == 'admin'""",
        }
        pr_context = {"pr_number": 42}

        result = await code_analyzer.analyze_diff_impact(file_data, pr_context)

        assert isinstance(result, dict)
        assert "impact_score" in result
        assert "risk_level" in result
        assert "change_type" in result
        assert "affected_functions" in result
        assert "lines_added" in result
        assert "lines_removed" in result

        assert result["lines_added"] > 0
        assert result["lines_removed"] > 0
        assert isinstance(result["affected_functions"], list)

    @pytest.mark.unit
    def test_function_name_extraction(self, code_analyzer):
        """Test function name extraction from code lines."""
        test_cases = [
            ("def calculate_score(items):", "calculate_score"),
            ("    def process_data(self, data):", "process_data"),
            ("function processUser(user) {", "processUser"),
            ("class DataProcessor:", "DataProcessor"),
            ("var normalLine = 'not a function';", "unknown"),
        ]

        for line, expected in test_cases:
            result = code_analyzer._extract_function_name(line)
            assert result == expected

    @pytest.mark.unit
    def test_impact_score_calculation(self, code_analyzer):
        """Test impact score calculation for changes."""
        # Low impact change
        score_low = code_analyzer._calculate_impact_score(
            added_lines=2,
            removed_lines=1,
            modified_functions=0,
            file_data={"filename": "README.md"},
        )

        # High impact change
        score_high = code_analyzer._calculate_impact_score(
            added_lines=50,
            removed_lines=30,
            modified_functions=5,
            file_data={"filename": "core/engine.py"},
        )

        assert score_low < score_high
        assert 0 <= score_low <= 100
        assert 0 <= score_high <= 100

    @pytest.mark.unit
    def test_risk_level_determination(self, code_analyzer):
        """Test risk level determination logic."""
        # Low risk
        risk_low = code_analyzer._determine_risk_level(
            impact_score=15, file_data={"filename": "docs/README.md"}
        )
        assert risk_low == "low"

        # Medium risk
        risk_medium = code_analyzer._determine_risk_level(
            impact_score=45, file_data={"filename": "src/utils.py"}
        )
        assert risk_medium == "medium"

        # High risk
        risk_high = code_analyzer._determine_risk_level(
            impact_score=85, file_data={"filename": "core/security.py"}
        )
        assert risk_high == "high"

    @pytest.mark.unit
    def test_change_type_determination(self, code_analyzer):
        """Test change type determination."""
        # New file
        change_new = code_analyzer._determine_change_type(
            {"status": "added", "filename": "new_feature.py"}
        )
        assert change_new == "addition"

        # Deleted file
        change_deleted = code_analyzer._determine_change_type(
            {"status": "removed", "filename": "old_feature.py"}
        )
        assert change_deleted == "deletion"

        # Modified file
        change_modified = code_analyzer._determine_change_type(
            {"status": "modified", "filename": "existing.py"}
        )
        assert change_modified == "modification"

        # Renamed file
        change_renamed = code_analyzer._determine_change_type(
            {"status": "renamed", "filename": "new_name.py"}
        )
        assert change_renamed == "rename"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_file_summary_generation(self, code_analyzer):
        """Test file summary generation."""
        # Create mock file analysis
        file_analysis = Mock()
        file_analysis.file_name = "models.py"
        file_analysis.file_type = "python"
        file_analysis.quality_score = 78
        file_analysis.issues_count = 3
        file_analysis.critical_issues_count = 1
        file_analysis.lines_added = 25
        file_analysis.lines_removed = 5

        summary = await code_analyzer.generate_file_summary(file_analysis)

        assert isinstance(summary, str)
        assert "models.py" in summary
        assert "python" in summary
        assert "78" in summary
        assert "+25/-5" in summary

    @pytest.mark.unit
    def test_content_hash_calculation(self, code_analyzer):
        """Test content hash calculation for caching."""
        content1 = "def hello(): return 'world'"
        content2 = "def hello(): return 'universe'"
        content3 = "def hello(): return 'world'"  # Same as content1

        hash1 = code_analyzer._calculate_content_hash(content1)
        hash2 = code_analyzer._calculate_content_hash(content2)
        hash3 = code_analyzer._calculate_content_hash(content3)

        assert hash1 != hash2  # Different content
        assert hash1 == hash3  # Same content
        assert len(hash1) == 64  # SHA-256 hex length

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_error_handling_in_analysis(self, code_analyzer, mock_ai_agent):
        """Test error handling during file analysis."""
        # Mock AI agent to raise an exception
        mock_ai_agent.analyze_code_quality.side_effect = Exception(
            "AI service unavailable"
        )

        file_data = {
            "filename": "test.py",
            "status": "modified",
            "additions": 10,
            "deletions": 2,
            "patch": "some diff content",
        }
        pr_context = {"pr_number": 42}

        # Analysis should handle errors gracefully
        with pytest.raises(Exception):
            await code_analyzer.analyze_file(file_data, pr_context, mock_ai_agent)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_large_file_handling(self, code_analyzer, mock_ai_agent):
        """Test handling of large files."""
        # Create large file data
        large_content = "\n".join([f"# Line {i}" for i in range(10000)])

        with patch.object(
            code_analyzer, "_perform_comprehensive_analysis"
        ) as mock_analysis:
            mock_analysis.return_value = {
                "language": "python",
                "complexity_score": 15,
                "quality_score": 60,
                "security_score": 80,
                "maintainability_score": 50,
                "issues": [],
                "suggestions": [],
                "metrics": {
                    "total_lines": 10000,
                    "code_lines": 8000,
                    "duplication_score": 0.2,
                },
            }

            file_data = {
                "filename": "large_file.py",
                "status": "modified",
                "additions": 5000,
                "deletions": 1000,
                "content": large_content,
            }
            pr_context = {"pr_number": 42}

            result = await code_analyzer.analyze_file(
                file_data, pr_context, mock_ai_agent
            )

            assert isinstance(result, FileAnalysis)
            assert result.lines_total == 10000
            assert result.lines_analyzed == 8000
