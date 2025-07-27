# Autonomous Code Review Agent System

An AI-powered system that automatically analyzes GitHub pull requests using advanced language models and provides structured feedback through a REST API. Built with FastAPI, Celery, and LangGraph for scalable, asynchronous code review processing.

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI App   │    │  Celery Worker  │    │   AI Agent      │
│                 │    │                 │    │  (LangGraph)    │
│ • REST API      │────│ • PR Analysis   │────│ • Code Review   │
│ • Task Queue    │    │ • GitHub API    │    │ • LLM Analysis  │
│ • Status Check  │    │ • Error Handle  │    │ • Structured    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │   RabbitMQ      │    │     Redis       │
│                 │    │                 │    │                 │
│ • Task Results  │    │ • Message Queue │    │ • Cache         │
│ • PR Metadata   │    │ • Job Queue     │    │ • Session Store │
│ • Analysis Data │    │ • Retry Logic   │    │ • Rate Limiting │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🚀 Features

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

## 📦 Installation & Setup

### Prerequisites
- Python 3.8+
- Docker & Docker Compose
- Git

### Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd code-review-agent
   ```

2. **Set up the development environment**
   ```bash
   make setup-dev
   ```

3. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Start infrastructure services**
   ```bash
   make docker-up
   ```

5. **Run the application**
   ```bash
   make run-dev
   ```

### Manual Installation

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment variables**
   ```bash
   export OPENROUTER_API_KEY="your-openrouter-api-key"
   export GITHUB_TOKEN="your-github-token"
   # ... other environment variables
   ```

3. **Start services**
   ```bash
   # Start PostgreSQL, Redis, RabbitMQ
   docker-compose up -d postgres redis rabbitmq
   
   # Start Celery worker
   celery -A app.worker.celery_app worker --loglevel=info
   
   # Start FastAPI app
   uvicorn app.main:app --reload
   ```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENROUTER_API_KEY` | OpenRouter API key | Required |
| `GITHUB_TOKEN` | GitHub personal access token | Optional |
| `DATABASE_URL` | PostgreSQL connection URL | `postgresql://...` |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |
| `CELERY_BROKER_URL` | Celery broker URL | `amqp://guest:guest@localhost:5672//` |
| `AI_OPENROUTER_MODEL` | OpenRouter model name | `qwen/qwen3-coder:free` |

### AI Model Configuration

#### OpenRouter (Default)
```bash
export OPENROUTER_API_KEY="your-api-key-here"
export AI_OPENROUTER_MODEL="qwen/qwen3-coder:free"
export AI_TEMPERATURE=0.1
```

## 📚 API Documentation

### Endpoints

#### 1. Analyze Pull Request
```http
POST /api/v1/analyze-pr
Content-Type: application/json

{
  "repo_url": "https://github.com/user/repo",
  "pr_number": 123,
  "github_token": "optional_token"
}
```

**Response:**
```json
{
  "task_id": "abc123",
  "status": "pending",
  "message": "PR analysis started"
}
```

#### 2. Check Task Status
```http
GET /api/v1/status/{task_id}
```

**Response:**
```json
{
  "task_id": "abc123",
  "status": "processing|completed|failed",
  "progress": 50,
  "message": "Analyzing files..."
}
```

#### 3. Get Analysis Results
```http
GET /api/v1/results/{task_id}
```

**Response:**
```json
{
  "task_id": "abc123",
  "status": "completed",
  "results": {
    "files": [
      {
        "name": "main.py",
        "issues": [
          {
            "type": "style",
            "line": 15,
            "description": "Line too long",
            "suggestion": "Break line into multiple lines",
            "severity": "low"
          }
        ]
      }
    ],
    "summary": {
      "total_files": 1,
      "total_issues": 1,
      "critical_issues": 0
    }
  }
}
```

## 🛠️ Development

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
make celery-flower      # Start Flower monitoring
```

### Project Structure

```
app/
├── main.py                 # FastAPI application entry point
├── config.py              # Configuration management
├── database.py            # Database setup and connection
├── api/                   # API endpoints and routes
│   ├── __init__.py
│   ├── schemas.py         # Pydantic models for API
│   └── pr_analysis.py     # PR analysis endpoints
├── models/                # SQLAlchemy database models
│   ├── __init__.py
│   ├── task.py           # Task model
│   └── pr_analysis.py    # PR analysis results model
├── services/             # Business logic services
│   ├── __init__.py
│   ├── github_client.py  # GitHub API client
│   ├── ai_agent.py       # AI agent implementation
│   └── code_analyzer.py  # Code analysis utilities
├── worker/               # Celery tasks and workers
│   ├── __init__.py
│   ├── celery_app.py     # Celery configuration
│   ├── celery_worker.py  # Worker tasks
│   └── pr_analysis_task.py # PR analysis task
└── utils/                # Utility modules
    ├── __init__.py
    ├── logger.py         # Logging utilities
    └── exceptions.py     # Custom exceptions
```

### Code Style & Standards

- **Black** for code formatting
- **isort** for import sorting
- **mypy** for type checking
- **flake8** for linting
- **bandit** for security checks
- **pytest** for testing

### Testing

```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run specific test file
pytest tests/test_specific.py -v

# Run integration tests
pytest tests/ -m integration
```

## 🔍 Monitoring & Debugging

### Celery Flower
Access Celery monitoring at: http://localhost:5555
- Username: `guest`
- Password: `guest`

### Logs
```bash
# Application logs
make docker-logs

# Specific service logs
docker-compose logs -f app
docker-compose logs -f celery-worker
```

### Health Checks
```bash
# Check API health
curl http://localhost:8000/health

# Check database connection
curl http://localhost:8000/health/db

# Check Redis connection
curl http://localhost:8000/health/redis
```

## 🚀 Deployment

### Production Checklist

1. **Environment Configuration**
   - [ ] Set `ENVIRONMENT=production`
   - [ ] Configure secure `SECRET_KEY`
   - [ ] Set up production database
   - [ ] Configure proper CORS origins

2. **Security**
   - [ ] Enable HTTPS
   - [ ] Set up proper authentication
   - [ ] Configure rate limiting
   - [ ] Review security settings

3. **Performance**
   - [ ] Configure connection pooling
   - [ ] Set up caching
   - [ ] Optimize worker concurrency
   - [ ] Monitor resource usage

4. **Monitoring**
   - [ ] Set up application monitoring
   - [ ] Configure error tracking
   - [ ] Set up log aggregation
   - [ ] Monitor performance metrics

### Docker Production Deployment

1. **Build production image**
   ```bash
   docker build -t code-review-agent:latest .
   ```

2. **Deploy with docker-compose**
   ```bash
   ENVIRONMENT=production docker-compose -f docker-compose.prod.yml up -d
   ```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-feature`
3. Make changes and add tests
4. Run quality checks: `make check-all`
5. Commit changes: `git commit -am 'Add new feature'`
6. Push to branch: `git push origin feature/new-feature`
7. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

- **Documentation**: Check this README and inline code documentation
- **Issues**: Report bugs and request features via GitHub Issues
- **Discussions**: Join discussions in GitHub Discussions

## 🔮 Future Enhancements

- [ ] Support for more programming languages
- [ ] Integration with more AI models
- [ ] GitHub webhook support for automatic analysis
- [ ] Web dashboard for results visualization
- [ ] Team collaboration features
- [ ] Custom analysis rules and configurations
- [ ] Performance analytics and insights
