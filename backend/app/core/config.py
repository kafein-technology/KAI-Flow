"""Configuration management for Agent-Flow V2.

Handles application settings using constants from constants.py.
All environment variables are defined in constants.py.
"""

import os
import logging
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
    
    

def setup_langsmith():
    """Setup LangSmith tracing if enabled"""
    if LANGCHAIN_TRACING_V2:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        if LANGCHAIN_ENDPOINT:
            os.environ["LANGCHAIN_ENDPOINT"] = LANGCHAIN_ENDPOINT
        if LANGCHAIN_API_KEY:
            os.environ["LANGCHAIN_API_KEY"] = LANGCHAIN_API_KEY
        if LANGCHAIN_PROJECT:
            os.environ["LANGCHAIN_PROJECT"] = LANGCHAIN_PROJECT
        logging.info("LangSmith tracing enabled")



def create_directories():
    """Create necessary directories"""
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)
        logging.info(f"Created upload directory: {UPLOAD_DIR}")

def get_database_url() -> str:
    """Get database URL for direct connections"""
    return DATABASE_URL

def get_cors_origins() -> List[str]:
    """Get CORS origins"""
    # Parse CORS origins if it's a string
    origins = []
    if isinstance(ALLOWED_ORIGINS, str):
        origins = [origin.strip() for origin in ALLOWED_ORIGINS.split(',')]
    else:
        origins = ALLOWED_ORIGINS
    
    # Add dynamic origins based on environment
    if DEBUG:
        origins.extend([
            "http://localhost:*",
            "https://localhost:*"
        ])
    
    return origins