# -*- coding: utf-8 -*-
"""
Export functionality router - Modular version.

This file now serves as a simple bridge to the modular export system.
The heavy lifting is done by the export package modules:
- schemas.py: Pydantic models
- utils.py: Helper functions
- services.py: Business logic
- routes.py: API endpoints
"""

# Import everything from the modular export package
from .export import *
import logging

# The router is now defined in routes.py and imported here
# This ensures backward compatibility while providing a clean modular structure

logger = logging.getLogger(__name__)

# System environment variables (minimal set for runtime)
SYSTEM_ENV_VARS = {
    "DATABASE_URL": "PostgreSQL database connection URL",
    "SECRET_KEY": "Secret key for JWT authentication",
    "WORKFLOW_ID": "Workflow identifier",
    "API_KEYS": "Comma-separated API keys",
    "REQUIRE_API_KEY": "API key authentication required"
}

<<<<<<< HEAD

=======
>>>>>>> serialization_fixes
logger.info("MODULAR EXPORT: Loaded from modular export package")
logger.info(f"Available functions: {len(__all__)} functions exported")
logger.info(f"Router: {router}")

# Export the router for main app.py to use
__all__ = ["router"] + list(locals().keys())
