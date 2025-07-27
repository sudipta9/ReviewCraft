#!/usr/bin/env python3
"""
Test runner script for the autonomous code review system.

This script provides convenient commands for running different types of tests
and generating reports.
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: list, description: str) -> bool:
    """Run a command and return success status."""
    print(f"\n🔧 {description}")
    print("=" * 50)
    
    try:
        subprocess.run(cmd, check=True, cwd=Path(__file__).parent)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed with exit code {e.returncode}")
        return False


def run_unit_tests():
    """Run unit tests only."""
    return run_command(
        ["python", "-m", "pytest", "tests/unit/", "-v", "-m", "unit"],
        "Running unit tests"
    )


def run_integration_tests():
    """Run integration tests only."""
    return run_command(
        ["python", "-m", "pytest", "tests/integration/", "-v", "-m", "integration"],
        "Running integration tests"
    )


def run_all_tests():
    """Run all tests."""
    return run_command(
        ["python", "-m", "pytest", "tests/", "-v"],
        "Running all tests"
    )


def run_tests_with_coverage():
    """Run tests with coverage report."""
    return run_command(
        ["python", "-m", "pytest", "tests/", "-v", "--cov=app", "--cov-report=html"],
        "Running tests with coverage"
    )


def run_fast_tests():
    """Run fast tests only (excluding slow tests)."""
    return run_command(
        ["python", "-m", "pytest", "tests/", "-v", "-m", "not slow"],
        "Running fast tests"
    )


def check_test_quality():
    """Check test code quality."""
    print("\n🔍 Checking test code quality")
    print("=" * 50)
    
    # Check if tests exist
    test_files = list(Path("tests").rglob("test_*.py"))
    print(f"Found {len(test_files)} test files:")
    for test_file in test_files:
        print(f"  - {test_file}")
    
    if not test_files:
        print("❌ No test files found!")
        return False
    
    print("✅ Test files found")
    return True


def main():
    """Main test runner."""
    if len(sys.argv) < 2:
        print("🧪 Test Runner for Autonomous Code Review System")
        print("=" * 50)
        print("Usage: python run_tests.py <command>")
        print("\nAvailable commands:")
        print("  unit        - Run unit tests only")
        print("  integration - Run integration tests only")
        print("  all         - Run all tests")
        print("  coverage    - Run tests with coverage report")
        print("  fast        - Run fast tests (exclude slow)")
        print("  quality     - Check test quality and coverage")
        print("\nExamples:")
        print("  python run_tests.py unit")
        print("  python run_tests.py coverage")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "unit":
        success = run_unit_tests()
    elif command == "integration":
        success = run_integration_tests()
    elif command == "all":
        success = run_all_tests()
    elif command == "coverage":
        success = run_tests_with_coverage()
    elif command == "fast":
        success = run_fast_tests()
    elif command == "quality":
        success = check_test_quality()
    else:
        print(f"❌ Unknown command: {command}")
        print("Available commands: unit, integration, all, coverage, fast, quality")
        sys.exit(1)
    
    if success:
        print(f"\n🎉 Command '{command}' completed successfully!")
        sys.exit(0)
    else:
        print(f"\n💥 Command '{command}' failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
