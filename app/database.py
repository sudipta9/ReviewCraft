"""
Database Configuration and Setup Module

This module provides database connection management, session handling,
and base model configuration using SQLAlchemy with async support.

Features:
- Async database connection pooling
- Session management with proper cleanup
- Base model with common fields
- Database initialization and health checks
- Connection retry logic with tenacity
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator, Optional
from uuid import uuid4

from sqlalchemy import DateTime, String, event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import NullPool
from sqlalchemy.sql import func
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.utils.logger import LoggerMixin, get_logger

logger = get_logger(__name__)


class Base(DeclarativeBase):
    """
    Base class for all database models.

    This class provides common functionality and fields that should be
    available in all database models.

    Common fields:
    - id: Primary key (UUID)
    - created_at: Timestamp when record was created
    - updated_at: Timestamp when record was last updated
    """

    # Primary key as UUID
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        doc="Unique identifier for the record",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        doc="Timestamp when the record was created",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        doc="Timestamp when the record was last updated",
    )


class DatabaseManager(LoggerMixin):
    """
    Database manager for handling connections, sessions, and health checks.

    This class follows the singleton pattern to ensure consistent database
    configuration throughout the application lifecycle.
    """

    _instance: Optional["DatabaseManager"] = None
    _engine: Optional[AsyncEngine] = None
    _session_factory: Optional[async_sessionmaker[AsyncSession]] = None

    def __new__(cls) -> "DatabaseManager":
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize database manager."""
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self.logger.info("Initializing database manager")

    @property
    def engine(self) -> AsyncEngine:
        """Get database engine, creating it if necessary."""
        if self._engine is None:
            self._engine = self._create_engine()
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Get session factory, creating it if necessary."""
        if self._session_factory is None:
            self._session_factory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=True,
                autocommit=False,
            )
        return self._session_factory

    def _create_engine(self) -> AsyncEngine:
        """
        Create database engine with appropriate configuration.

        Returns:
            AsyncEngine: Configured database engine
        """
        # For async engines, we don't need to specify poolclass
        # SQLAlchemy will choose the appropriate async pool automatically
        if settings.is_testing:
            # Use NullPool for testing to avoid connection issues
            poolclass = NullPool
            pool_pre_ping = False
        else:
            # Let SQLAlchemy choose the appropriate async pool
            poolclass = None
            pool_pre_ping = True

        # Build engine kwargs
        engine_kwargs = {
            "echo": settings.database.echo,
            "pool_pre_ping": pool_pre_ping,
            "pool_recycle": 3600,  # Recycle connections every hour
        }

        # Only add pool configuration if not using NullPool
        if poolclass is not None:
            engine_kwargs["poolclass"] = poolclass
        else:
            engine_kwargs.update(
                {
                    "pool_size": settings.database.pool_size,
                    "max_overflow": settings.database.max_overflow,
                }
            )

        # Add PostgreSQL-specific connection args
        if "postgresql" in settings.database.url:
            engine_kwargs["connect_args"] = {
                "server_settings": {
                    "application_name": settings.app_name,
                    "timezone": "UTC",
                }
            }

        engine = create_async_engine(settings.database.url, **engine_kwargs)

        # Add logging for connection events
        if settings.is_development:

            @event.listens_for(engine.sync_engine, "connect")
            def on_connect(dbapi_connection, connection_record):
                self.logger.debug("Database connection established")

            @event.listens_for(engine.sync_engine, "close")
            def on_close(dbapi_connection, connection_record):
                self.logger.debug("Database connection closed")

        self.logger.info(
            "Database engine created",
            url=settings.database.url.split("@")[0] + "@[HIDDEN]",  # Hide credentials
            pool_size=settings.database.pool_size,
            max_overflow=settings.database.max_overflow,
        )

        return engine

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get database session with automatic cleanup.

        Yields:
            AsyncSession: Database session

        Example:
            async with db_manager.get_session() as session:
                result = await session.execute(select(User))
        """
        async with self.session_factory() as session:
            try:
                self.logger.debug("Database session created")
                yield session
            except Exception as e:
                self.logger.error("Database session error", error=str(e))
                await session.rollback()
                raise
            finally:
                await session.close()
                self.logger.debug("Database session closed")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    async def health_check(self) -> bool:
        """
        Perform database health check.

        Returns:
            bool: True if database is healthy, False otherwise
        """
        try:
            async with self.get_session() as session:
                result = await session.execute(text("SELECT 1"))
                result.fetchone()
                self.logger.debug("Database health check passed")
                return True
        except Exception as e:
            self.logger.error("Database health check failed", error=str(e))
            return False

    async def create_tables(self) -> None:
        """
        Create all database tables.

        This method should only be used in development or for initial setup.
        In production, use Alembic migrations instead.
        """
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.logger.info("Database tables created")

    async def drop_tables(self) -> None:
        """
        Drop all database tables.

        WARNING: This will delete all data! Only use in testing.
        """
        if not settings.is_testing:
            raise ValueError("drop_tables can only be used in testing environment")

        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        self.logger.warning("Database tables dropped")

    async def close(self) -> None:
        """Close database engine and all connections."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            self.logger.info("Database engine closed")


# Global database manager instance
db_manager = DatabaseManager()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for getting database session.

    Yields:
        AsyncSession: Database session

    Example:
        @app.get("/users/")
        async def get_users(db: AsyncSession = Depends(get_db_session)):
            result = await db.execute(select(User))
            return result.scalars().all()
    """
    async with db_manager.get_session() as session:
        yield session


async def init_database() -> None:
    """
    Initialize database connection and perform health check.

    This function should be called during application startup.
    """
    logger.info("Initializing database connection")

    # Perform health check
    is_healthy = await db_manager.health_check()
    if not is_healthy:
        raise RuntimeError("Database health check failed")

    logger.info("Database initialized successfully")


async def close_database() -> None:
    """
    Close database connections.

    This function should be called during application shutdown.
    """
    logger.info("Closing database connections")
    await db_manager.close()
    logger.info("Database connections closed")


# Utility functions for testing
async def reset_database() -> None:
    """
    Reset database by dropping and recreating all tables.

    WARNING: This will delete all data! Only use in testing.
    """
    if not settings.is_testing:
        raise ValueError("reset_database can only be used in testing environment")

    await db_manager.drop_tables()
    await db_manager.create_tables()
    logger.warning("Database reset completed")


async def wait_for_database(max_retries: int = 30, delay: float = 1.0) -> None:
    """
    Wait for database to become available.

    This is useful when starting the application with docker-compose
    where the database might not be immediately available.

    Args:
        max_retries: Maximum number of retry attempts
        delay: Delay between retries in seconds
    """
    for attempt in range(max_retries):
        try:
            is_healthy = await db_manager.health_check()
            if is_healthy:
                logger.info("Database is available")
                return
        except Exception as e:
            logger.warning(
                "Database not yet available",
                attempt=attempt + 1,
                max_retries=max_retries,
                error=str(e),
            )

        if attempt < max_retries - 1:
            await asyncio.sleep(delay)

    raise RuntimeError(f"Database not available after {max_retries} attempts")
