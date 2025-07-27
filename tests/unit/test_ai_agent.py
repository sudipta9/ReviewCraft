"""
Unit tests for the AI Agent service.

Tests cover code quality analysis, security scanning, language-specific
analysis, and summary generation functionality.
"""

from unittest.mock import Mock, patch

import pytest

from app.services.ai_agent import AIAgent


class TestAIAgent:
    """Test suite for AIAgent service."""

    @pytest.fixture
    def ai_agent(self, mock_settings):
        """Create AI agent instance for testing."""
        with patch("app.services.ai_agent.get_settings", return_value=mock_settings):
            return AIAgent()

    @pytest.mark.unit
    def test_agent_initialization(self, ai_agent):
        """Test AI agent initialization."""
        assert ai_agent is not None
        assert hasattr(ai_agent, "analysis_rules")
        assert "code_quality" in ai_agent.analysis_rules
        assert "security" in ai_agent.analysis_rules

    @pytest.mark.unit
    def test_language_detection(self, ai_agent):
        """Test programming language detection."""
        assert ai_agent._detect_language("main.py") == "python"
        assert ai_agent._detect_language("app.js") == "javascript"
        assert ai_agent._detect_language("component.tsx") == "typescript"
        assert ai_agent._detect_language("style.css") == "css"
        assert ai_agent._detect_language("README.md") == "markdown"
        assert ai_agent._detect_language("unknown.xyz") == "unknown"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_code_quality_analysis(self, ai_agent, sample_python_code):
        """Test code quality analysis functionality."""
        result = await ai_agent.analyze_code_quality(sample_python_code, "test.py")

        assert isinstance(result, dict)
        assert "total_lines" in result
        assert "code_lines" in result
        assert "complexity_score" in result
        assert "duplication_score" in result
        assert "language" in result
        assert "maintainability_score" in result
        assert result["language"] == "python"
        assert result["total_lines"] > 0
        assert result["complexity_score"] >= 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_security_analysis_sql_injection(self, ai_agent):
        """Test security analysis for SQL injection detection."""
        code_with_sql_injection = """
        def get_user(user_id):
            query = "SELECT * FROM users WHERE id = " + user_id
            return execute_query(query)
        """

        result = await ai_agent.analyze_security(
            code_with_sql_injection, "vulnerable.py"
        )

        assert isinstance(result, list)
        sql_injection_issues = [
            issue for issue in result if issue["type"] == "sql_injection"
        ]
        assert len(sql_injection_issues) > 0
        assert sql_injection_issues[0]["severity"] == "high"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_security_analysis_xss(self, ai_agent):
        """Test security analysis for XSS detection."""
        code_with_xss = """
        function updateContent(userInput) {
            document.getElementById("content").innerHTML = userInput;
        }
        """

        result = await ai_agent.analyze_security(code_with_xss, "vulnerable.js")

        assert isinstance(result, list)
        xss_issues = [issue for issue in result if issue["type"] == "xss"]
        assert len(xss_issues) > 0
        assert xss_issues[0]["severity"] == "medium"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_security_analysis_sensitive_data(self, ai_agent, sample_python_code):
        """Test security analysis for sensitive data detection."""
        result = await ai_agent.analyze_security(sample_python_code, "test.py")

        assert isinstance(result, list)
        sensitive_data_issues = [
            issue for issue in result if issue["type"] == "sensitive_data"
        ]
        assert len(sensitive_data_issues) > 0
        assert sensitive_data_issues[0]["severity"] == "critical"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_python_specific_analysis(self, ai_agent, sample_python_code):
        """Test Python-specific code analysis."""
        result = await ai_agent._analyze_python_specific(sample_python_code)

        assert isinstance(result, list)

        # Check for missing type hints
        type_hint_issues = [issue for issue in result if issue["type"] == "typing"]
        assert len(type_hint_issues) > 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_javascript_specific_analysis(self, ai_agent, sample_javascript_code):
        """Test JavaScript-specific code analysis."""
        result = await ai_agent._analyze_javascript_specific(sample_javascript_code)

        assert isinstance(result, list)

        # Check for var usage
        var_issues = [issue for issue in result if "var" in issue["message"]]
        assert len(var_issues) > 0

        # Check for console.log
        console_issues = [
            issue for issue in result if "console.log" in issue["message"]
        ]
        assert len(console_issues) > 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_suggestions_generation(self, ai_agent, sample_python_code):
        """Test code improvement suggestions generation."""
        result = await ai_agent.generate_suggestions(sample_python_code, "test.py")

        assert isinstance(result, list)
        assert len(result) > 0

        # Check suggestion structure
        for suggestion in result:
            assert "type" in suggestion
            assert "priority" in suggestion
            assert "message" in suggestion
            assert "suggestion" in suggestion

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_complexity_calculation(self, ai_agent):
        """Test complexity calculation."""
        simple_code = "def simple(): return 1"
        complex_code = """
        def complex_function(x, y, z):
            if x > 0:
                if y > 0:
                    if z > 0:
                        for i in range(10):
                            if i % 2 == 0:
                                return i * x * y * z
            return 0
        """

        simple_complexity = await ai_agent._calculate_complexity(
            simple_code, "simple.py"
        )
        complex_complexity = await ai_agent._calculate_complexity(
            complex_code, "complex.py"
        )

        assert simple_complexity < complex_complexity
        assert complex_complexity > 5  # Should detect high complexity

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_duplication_detection(self, ai_agent):
        """Test code duplication detection."""
        code_with_duplication = """
        def process_data_a():
            result = []
            for item in data:
                result.append(item * 2)
            return result

        def process_data_b():
            result = []
            for item in data:
                result.append(item * 2)
            return result
        """

        duplication_score = await ai_agent._check_duplication(code_with_duplication)
        assert duplication_score > 0.2  # Should detect significant duplication

    @pytest.mark.unit
    def test_maintainability_score_calculation(self, ai_agent):
        """Test maintainability score calculation."""
        # Test different scenarios
        score_good = ai_agent._calculate_maintainability_score(100, 5, 0.1)
        score_bad = ai_agent._calculate_maintainability_score(500, 20, 0.8)

        assert score_good > score_bad
        assert 0 <= score_good <= 100
        assert 0 <= score_bad <= 100

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_summary_generation(self, ai_agent, mock_github_pr_data):
        """Test PR analysis summary generation."""
        # Mock file analyses
        mock_file_analyses = [
            Mock(quality_score=85, issues=[]),
            Mock(quality_score=70, issues=[Mock(severity="critical")]),
            Mock(quality_score=90, issues=[Mock(severity="low")]),
        ]

        result = await ai_agent.generate_summary(
            mock_github_pr_data, mock_file_analyses, 2
        )

        assert isinstance(result, dict)
        assert "overall_quality" in result
        assert "overall_score" in result
        assert "total_files_analyzed" in result
        assert "total_issues" in result
        assert "critical_issues" in result
        assert "recommendations" in result
        assert "analysis_timestamp" in result
        assert "pr_metadata" in result

        assert result["total_files_analyzed"] == 3
        assert result["total_issues"] == 2

    @pytest.mark.unit
    def test_analysis_rules_loading(self, ai_agent):
        """Test analysis rules are properly loaded."""
        rules = ai_agent.analysis_rules

        assert "code_quality" in rules
        assert "security" in rules
        assert "best_practices" in rules

        # Check code quality rules
        quality_rules = rules["code_quality"]
        assert "max_function_length" in quality_rules
        assert "complexity_threshold" in quality_rules

        # Check security rules
        security_rules = rules["security"]
        assert "sql_injection_patterns" in security_rules
        assert "xss_patterns" in security_rules
        assert "sensitive_data_patterns" in security_rules

        # Check best practices
        best_practices = rules["best_practices"]
        assert "python" in best_practices
        assert "javascript" in best_practices

    @pytest.mark.unit
    def test_function_length_estimation(self, ai_agent):
        """Test function length estimation."""
        code_with_functions = """
        def short_function():
            return 1
        def longer_function():
            x = 1
            y = 2
            z = x + y
            return z
        class TestClass:
            def method(self):
                pass
        """

        result = ai_agent._estimate_function_lengths(code_with_functions)

        assert isinstance(result, dict)
        assert len(result) > 0

        # Should detect multiple functions
        assert any("function" in name.lower() for name in result.keys())
