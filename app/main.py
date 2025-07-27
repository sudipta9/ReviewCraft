"""
FastAPI Application Factory

This module creates and configures the FastAPI application with all necessary
middleware, error handlers, and route configurations.

Features:
- Application lifecycle management
- Global error handling
- Request/response middleware
- CORS configuration
- Health checks
- API documentation
"""

import time
import uuid
from contextlib import asynccontextmanager

import orjson
import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.schemas import (
    ErrorDetail,
    ErrorResponse,
    HealthCheckResponse,
    HealthStatus,
)
from app.config import settings
from app.database import close_database, init_database
from app.utils import (
    BaseApplicationError,
    ErrorCode,
    get_logger,
    handle_exception,
    log_api_request,
    log_api_response,
)

logger = get_logger(__name__)


class ORJSONResponse(JSONResponse):
    """
    Custom JSON response using orjson for high performance and automatic datetime serialization.
    """

    def render(self, content) -> bytes:
        """Render content to JSON bytes using orjson."""
        return orjson.dumps(content)


# Application start time for uptime calculation
app_start_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles startup and shutdown events for the FastAPI application.
    """
    # Startup
    logger.info("Starting Code Review Agent API")

    try:
        # Initialize database connection
        await init_database()
        logger.info("Database initialized successfully")

        # Add any other startup tasks here
        # - Initialize AI models
        # - Setup caching
        # - Connect to external services

        logger.info("Application startup completed")
        yield

    except Exception as e:
        logger.error("Application startup failed", error=str(e))
        raise

    finally:
        # Shutdown
        logger.info("Shutting down Code Review Agent API")

        try:
            # Close database connections
            await close_database()
            logger.info("Database connections closed")

            # Add any other cleanup tasks here

            logger.info("Application shutdown completed")

        except Exception as e:
            logger.error("Error during application shutdown", error=str(e))


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.

    Returns:
        FastAPI: Configured application instance
    """
    # Create FastAPI instance
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Autonomous Code Review Agent API for analyzing GitHub pull requests",
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        openapi_url="/openapi.json" if settings.is_development else None,
        lifespan=lifespan,
        default_response_class=ORJSONResponse,  # Use orjson for all responses
    )

    # Configure middleware
    configure_middleware(app)

    # Configure error handlers
    configure_error_handlers(app)

    # Configure routes
    configure_routes(app)

    return app


def configure_middleware(app: FastAPI) -> None:
    """Configure application middleware."""

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request logging middleware
    @app.middleware("http")
    async def logging_middleware(request: Request, call_next):
        """Log all HTTP requests and responses."""
        # Generate request ID
        request_id = str(uuid.uuid4())

        # Add request ID to request state
        request.state.request_id = request_id

        # Log request
        start_time = time.time()
        log_api_request(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            additional_context={
                "query_params": dict(request.query_params),
                "user_agent": request.headers.get("user-agent"),
                "client_ip": request.client.host if request.client else None,
            },
        )

        # Process request
        try:
            response = await call_next(request)

            # Log response
            duration_ms = (time.time() - start_time) * 1000
            log_api_response(
                request_id=request_id,
                status_code=response.status_code,
                duration_ms=duration_ms,
            )

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            # Log error
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                "Request failed",
                request_id=request_id,
                error=str(e),
                duration_ms=duration_ms,
            )
            raise


def configure_error_handlers(app: FastAPI) -> None:
    """Configure global error handlers."""

    @app.exception_handler(BaseApplicationError)
    async def application_error_handler(request: Request, exc: BaseApplicationError):
        """Handle custom application errors."""
        logger.warning(
            "Application error",
            request_id=getattr(request.state, "request_id", "unknown"),
            error_code=exc.error_code.value,
            error_message=exc.message,
            context=exc.context,
        )

        return ORJSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                message=exc.message,
                error=ErrorDetail(
                    code=exc.error_code.value, message=exc.message, context=exc.context
                ),
            ).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        """Handle Pydantic validation errors."""
        logger.warning(
            "Validation error",
            request_id=getattr(request.state, "request_id", "unknown"),
            errors=exc.errors(),
        )

        # Format validation errors
        error_details = []
        for error in exc.errors():
            field = ".".join(str(loc) for loc in error["loc"])
            error_details.append(
                {"field": field, "message": error["msg"], "type": error["type"]}
            )

        return ORJSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorResponse(
                message="Input validation failed",
                error=ErrorDetail(
                    code=ErrorCode.VALIDATION_ERROR.value,
                    message="Input validation failed",
                    context={"details": error_details},
                ),
            ).model_dump(),
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error_handler(request: Request, exc: SQLAlchemyError):
        """Handle database errors."""
        logger.error(
            "Database error",
            request_id=getattr(request.state, "request_id", "unknown"),
            error=str(exc),
        )

        return ORJSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error=ErrorDetail(
                    code=ErrorCode.DATABASE_ERROR.value,
                    message="Database operation failed",
                )
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle unexpected errors."""
        logger.error(
            "Unexpected error",
            request_id=getattr(request.state, "request_id", "unknown"),
            error=str(exc),
            error_type=type(exc).__name__,
        )

        # Convert to application error
        app_error = handle_exception(exc)

        return ORJSONResponse(
            status_code=app_error.status_code,
            content=ErrorResponse(
                error=ErrorDetail(
                    code=app_error.error_code.value,
                    message=(
                        app_error.message
                        if settings.is_development
                        else "Internal server error"
                    ),
                    context=app_error.context if settings.is_development else None,
                )
            ).model_dump(),
        )


def configure_routes(app: FastAPI) -> None:
    """Configure application routes."""

    @app.get("/health", response_model=HealthCheckResponse, tags=["Health"])
    async def health_check():
        """
        Health check endpoint.

        Returns the current health status of the application and its dependencies.
        """
        from app.database import db_manager

        # Check database health
        db_healthy = await db_manager.health_check()

        # Calculate uptime
        uptime = time.time() - app_start_time

        # Determine overall status
        if db_healthy:
            overall_status = HealthStatus.HEALTHY
        else:
            overall_status = HealthStatus.UNHEALTHY

        return HealthCheckResponse(
            success=overall_status == HealthStatus.HEALTHY,
            message="Health check completed",
            status=overall_status,
            checks={
                "database": {
                    "status": "healthy" if db_healthy else "unhealthy",
                    "details": (
                        "Database connection successful"
                        if db_healthy
                        else "Database connection failed"
                    ),
                }
            },
            uptime=uptime,
            version=settings.app_version,
        )

    # Import and include API routers
    from app.api.pr_analysis import router as pr_analysis_router

    app.include_router(
        pr_analysis_router, prefix=settings.api_prefix, tags=["PR Analysis"]
    )


# Create the application instance
app = create_app()


if __name__ == "__main__":
    # Run the application directly (for development)
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.is_development,
        log_level=settings.logging.level.lower(),
    )
