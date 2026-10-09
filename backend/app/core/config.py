"""Configuration management for Agent-Flow V2.

Handles application settings using constants from constants.py.
All environment variables are defined in constants.py.
"""

import logging
import os
from typing import List

# Import all constants
from app.core.constants import *

def get_warnings() -> List[str]:
    """Get a list of configuration-related warnings."""
    warnings = []
    if SECRET_KEY == "your-secret-key-here-change-in-production":
        warnings.append("SECRET_KEY is not set, using default. THIS IS NOT SAFE FOR PRODUCTION.")

   

def setup_logging():
    """Setup logging configuration using comprehensive logging system"""
    from app.core.logging_config import setup_comprehensive_logging
    setup_comprehensive_logging()
    
    

_langsmith_client = None


def setup_langsmith():
    """Configure optional LangSmith tracing without mutating secret env vars."""

    global _langsmith_client
    from langsmith import Client, configure

    if not LANGSMITH_TRACING_ENABLED:
        configure(client=None, enabled=False, project_name=None)
        _langsmith_client = None
        logging.info("LangSmith tracing disabled")
        return None

    if not LANGSMITH_API_KEY:
        raise RuntimeError(
            "LangSmith tracing is enabled but no LangSmith API key is configured."
        )

    _langsmith_client = Client(
        api_url=LANGSMITH_ENDPOINT or None,
        api_key=LANGSMITH_API_KEY,
    )
    configure(
        client=_langsmith_client,
        enabled=True,
        project_name=LANGSMITH_PROJECT or "kai-flow",
    )
    logging.info("LangSmith tracing enabled")
    return _langsmith_client


def get_langsmith_client():
    """Return the explicitly configured client, if external tracing is enabled."""

    return _langsmith_client



def create_directories():
    """Create necessary directories"""
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)
        logging.info(f"Created upload directory: {UPLOAD_DIR}")

def get_database_url() -> str:
    """Get database URL for direct connections"""
    return DATABASE_URL
