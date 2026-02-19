"""
KAI-Flow Database Management - Clean & Simple Implementation
============================================================

Simple, standard SQLAlchemy database configuration with proper session management.
"""

import logging
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.pool import QueuePool

from app.core.constants import (
    DATABASE_URL, DISABLE_DATABASE,
    POSTGRES_USERNAME, POSTGRES_PASSWORD,
    DB_POOL_SIZE, DB_MAX_OVERFLOW, DB_POOL_TIMEOUT,
    DB_POOL_RECYCLE, DB_POOL_PRE_PING
)
from app.core.logging_config import log_database_operation

logger = logging.getLogger(__name__)

# Database engines
engine = None
async_engine = None
SessionLocal = None
AsyncSessionLocal = None

def create_database_url_variants(base_url: str) -> tuple[str, str]:
    """Create sync and async variants of database URL using psycopg3."""
    if not base_url:
        return None, None
    
    # For PostgreSQL, use psycopg3 (psycopg) for sync and asyncpg for async
    if base_url.startswith('postgresql://'):
        # Convert to psycopg3 for sync operations
        sync_url = base_url.replace('postgresql://', 'postgresql+psycopg://')
        async_url = base_url.replace('postgresql://', 'postgresql+asyncpg://')
    elif base_url.startswith('postgresql+psycopg2://'):
        # Convert old psycopg2 URLs to psycopg3
        sync_url = base_url.replace('postgresql+psycopg2://', 'postgresql+psycopg://')
        async_url = base_url.replace('postgresql+psycopg2://', 'postgresql+asyncpg://')
    elif base_url.startswith('postgresql+psycopg://'):
        # Already using psycopg3
        sync_url = base_url
        async_url = base_url.replace('postgresql+psycopg://', 'postgresql+asyncpg://')
    elif base_url.startswith('postgresql+asyncpg://'):
        async_url = base_url
        sync_url = base_url.replace('postgresql+asyncpg://', 'postgresql+psycopg://')
    else:
        # For other databases (SQLite, etc.), use the same URL
        sync_url = base_url
        async_url = base_url
    
    return sync_url, async_url

def build_database_url() -> str:
    """Build or modify DATABASE_URL with username/password if provided."""
    database_url = DATABASE_URL
    
    # If no DATABASE_URL provided, we can't build one without more info
    if not database_url:
        logger.info("No DATABASE_URL provided")
        return None
    
    # If username/password are provided, inject them into the URL
    if POSTGRES_USERNAME and POSTGRES_PASSWORD:
        import re
        
        # Handle two URL formats:
        # Format 1: postgresql://username:password@host:port/database (replace credentials)
        # Format 2: postgresql://host:port/database (inject credentials)
        
        # Try format 1 first (with existing credentials)
        pattern_with_creds = r'postgresql://([^:]+):([^@]+)@(.+)'
        match_with_creds = re.match(pattern_with_creds, database_url)
        
        if match_with_creds:
            # Replace existing username and password
            host_port_db = match_with_creds.group(3)
            modified_url = f"postgresql://{POSTGRES_USERNAME}:{POSTGRES_PASSWORD}@{host_port_db}"
            logger.info(f"Replaced existing credentials with user: {POSTGRES_USERNAME}")
            return modified_url
        
        # Try format 2 (no existing credentials)
        pattern_no_creds = r'postgresql://(.+)'
        match_no_creds = re.match(pattern_no_creds, database_url)
        
        if match_no_creds:
            # Inject credentials into URL without them
            host_port_db = match_no_creds.group(1)
            modified_url = f"postgresql://{POSTGRES_USERNAME}:{POSTGRES_PASSWORD}@{host_port_db}"
            logger.info(f"Injected credentials into DATABASE_URL for user: {POSTGRES_USERNAME}")
            return modified_url
        
        # If neither pattern matches, something is wrong
        logger.error(f"Unrecognized DATABASE_URL format: {database_url}")
        return database_url
    
    # Use DATABASE_URL as-is
    return database_url

def initialize_database():
    """Initialize database engines and session factories."""
    global engine, async_engine, SessionLocal, AsyncSessionLocal
    
    if DISABLE_DATABASE:
        logger.info("Database is disabled")
        return
    
    # Build database URL
    database_url = build_database_url()
    if not database_url:
        logger.info("Database configuration not provided - set DATABASE_URL")
        return
    
    try:
        # Create URL variants
        sync_url, async_url = create_database_url_variants(database_url)
        
        # Mask password in logs
        masked_url = database_url
        if POSTGRES_PASSWORD and POSTGRES_PASSWORD in database_url:
            masked_url = database_url.replace(POSTGRES_PASSWORD, '***')
        elif ':' in database_url and '@' in database_url:
            # Generic password masking for any URL with credentials
            import re
            masked_url = re.sub(r'://([^:]+):([^@]+)@', r'://\1:***@', database_url)
        
        logger.info(f"Database URL configured: {masked_url}")
        
        # Connection pool configuration for sync engine
        sync_connection_args = {
            "pool_size": DB_POOL_SIZE,
            "max_overflow": DB_MAX_OVERFLOW,
            "pool_timeout": DB_POOL_TIMEOUT,
            "pool_recycle": DB_POOL_RECYCLE,
            "pool_pre_ping": DB_POOL_PRE_PING,
            "poolclass": QueuePool,
            "echo": False,
        }
        
        # Connection pool configuration for async engine (no poolclass)
        async_connection_args = {
            "pool_size": DB_POOL_SIZE,
            "max_overflow": DB_MAX_OVERFLOW,
            "pool_timeout": DB_POOL_TIMEOUT,
            "pool_recycle": DB_POOL_RECYCLE,
            "pool_pre_ping": DB_POOL_PRE_PING,
            "echo": False,
        }
        
        # Create synchronous engine
        if sync_url:
            engine = create_engine(sync_url, **sync_connection_args)
            SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=engine
            )
            logger.info("Synchronous database engine initialized")
        
        # Create asynchronous engine
        if async_url:
            async_engine = create_async_engine(async_url, **async_connection_args)
            AsyncSessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=async_engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            logger.info("Asynchronous database engine initialized")
            
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
    # Don't raise during import - let the application start without database if needed
    logger.warning("Database initialization failed - some features may not work")

# Initialize database on import, but don't fail if it doesn't work
try:
    initialize_database()
except Exception as e:
    logger.warning(f"Database initialization failed during import: {e}")
    logger.info("Application will continue without database - some features may be limited")

# Synchronous database dependency
def get_db() -> Generator:
    """Get database session dependency for FastAPI."""
    if not SessionLocal:
        raise RuntimeError("Database is not enabled. Set DATABASE_URL to enable database functionality.")
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Asynchronous database dependency  
async def get_db_session():
    """Get async database session dependency for FastAPI."""
    if not AsyncSessionLocal:
        raise RuntimeError("Database is not enabled. Set DATABASE_URL to enable database functionality.")
    
    async with AsyncSessionLocal() as session:
        yield session

def get_db_session_context():
    """Get database session as async context manager for manual usage."""
    if not AsyncSessionLocal:
        raise RuntimeError("Database is not enabled. Set DATABASE_URL to enable database functionality.")
    return AsyncSessionLocal()

async def check_database_health() -> dict:
    """Perform a simple database health check."""
    if not AsyncSessionLocal:
        return {
            "healthy": False,
            "error": "Database is disabled",
            "response_time_ms": 0
        }
    
    import time
    start_time = time.time()
    
    try:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import text
            result = await session.execute(text("SELECT 1"))
            row = result.fetchone()
            
            response_time = (time.time() - start_time) * 1000
            
            if row and row[0] == 1:
                return {
                    "healthy": True,
                    "response_time_ms": round(response_time, 2)
                }
            else:
                return {
                    "healthy": False,
                    "error": "Health check query failed",
                    "response_time_ms": round(response_time, 2)
                }
                
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        return {
            "healthy": False,
            "error": str(e),
            "response_time_ms": round(response_time, 2)
        }

def get_database_stats() -> dict:
    """Get basic database statistics."""
    if not DATABASE_URL:
        return {
            "database_enabled": False,
            "message": "Database is disabled"
        }
    
    stats = {
        "database_enabled": True,
        "sync_engine": engine is not None,
        "async_engine": async_engine is not None,
        "database_url_set": bool(DATABASE_URL)
    }
    
    # Get pool status if available
    if engine and hasattr(engine, 'pool'):
        try:
            pool = engine.pool
            stats["pool_status"] = {
                "size": pool.size(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
                "checked_in": pool.checkedin()
            }
        except Exception as e:
            stats["pool_error"] = str(e)
    
    return stats
