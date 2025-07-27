# Autonomous Code Review Agent System

An AI-powered system that automatically analyzes GitHub pull requests using advanced language models and provides structured feedback through a REST API. Built with FastAPI, Celery, and LLM for scalable, asynchronous code review processing.

## Architecture Overview

(\*) marked are not yet implemented.

```text
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI App   │    │  Celery Worker  │    │   AI Agent      │
│                 │    │                 │    │    (LLM)        │
│ • REST API      │────│ • PR Analysis   │────│ • Code Review   │
│ • Task Queue    │    │ • GitHub API    │    │ • LLM Analysis  │
│ • Status Check  │    │ • Error Handle  │    │ • Structured    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────┐
│   PostgreSQL    │    │   RabbitMQ      │    │     Redis           │
│                 │    │                 │    │                     │
│ • Task Results  │    │ • Message Queue │    │ • Cache             │
│ • PR Metadata   │    │ • Job Queue     │    │ • Session Store (*) │
│ • Analysis Data │    │ • Retry Logic   │    │ • Rate Limiting(*)  │
└─────────────────┘    └─────────────────┘    └─────────────────────┘
```

## Features

### Core Functionality

- **Asynchronous PR Analysis**: Process GitHub pull requests in the background
- **AI-Powered Review**: Uses advanced LLMs via OpenRouter for cost-effective AI analysis
- **Multi-Language Support**: Analyzes Python, JavaScript, TypeScript, and more
- **Structured Output**: Returns consistent, actionable feedback

### Analysis Capabilities

- **Code Style & Formatting**: Identifies style violations and formatting issues
- **Bug Detection**: Finds potential bugs, null pointer exceptions, and logic errors
- **Performance Analysis**: Suggests optimizations and performance improvements
- **Best Practices**: Recommends industry best practices and design patterns
- **Security Issues**: Detects common security vulnerabilities

### Technical Features

- **Scalable Architecture**: Horizontal scaling with Celery workers
- **Rate Limiting**: Built-in rate limiting for GitHub API and AI services
- **Caching**: Intelligent caching of results and GitHub data
- **Monitoring**: Comprehensive logging and monitoring with Flower
- **Error Handling**: Robust error handling with retry logic

## Installation & Setup

### Prerequisites

- Python 3.8+
- Docker & Docker Compose
- Git

### Installation

1. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment variables**: Copy `.env.example` and fill with your configurations

3. **Start services**

   ```bash
   # Start PostgreSQL, Redis, RabbitMQ
   docker-compose up --file compose.yml -d

   # Start Celery worker
   make celery-worker

   # Start FastAPI app
   make run-dev
   ```

## Configuration

### Environment Variables

Checkout `.env.example`

### Available Commands

```bash
# Development
make setup-dev          # Set up development environment
make run-dev            # Run in development mode
make dev-start          # Start infrastructure and app

# Code Quality
make lint               # Run linting
make format             # Format code
make type-check         # Run type checking
make test               # Run tests
make test-cov           # Run tests with coverage
make check-all          # Run all quality checks

# Docker
make docker-up          # Start all services
make docker-down        # Stop all services
make docker-logs        # View logs

# Celery
make celery-worker      # Start Celery worker
```

## Future Enhancements

- [ ] Support for custom MCP and advanced language models like (claude 4, gemini, chatgpt etc.)
- [ ] GitHub webhook support for automatic analysis
- [ ] Web dashboard for results visualization
- [ ] Web framework testing using Playwright MCP
- [ ] Custom analysis rules and configurations
- [ ] Performance analytics and insights
- [ ] Request caching
