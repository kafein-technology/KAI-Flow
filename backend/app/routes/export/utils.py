<<<<<<< HEAD
# -*- coding: utf-8 -*-
"""Export utility functions."""

import logging
import uuid
import os
import tempfile
import zipfile
import json
import re
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.core.dynamic_node_analyzer import DynamicNodeAnalyzer
from app.core.node_registry import node_registry
from .schemas import WorkflowDependencies, EnvironmentVariable
from app.core.constants import API_START,API_VERSION

logger = logging.getLogger(__name__)

# Initialize dynamic analyzer
dynamic_analyzer = DynamicNodeAnalyzer(node_registry)

def analyze_workflow_dependencies(flow_data: Dict[str, Any]) -> WorkflowDependencies:
    """Dynamic workflow dependency analysis using DynamicNodeAnalyzer."""
    logger.info("🔍 Starting dynamic workflow dependency analysis")
    
    try:
        # Initialize dynamic analyzer with node registry
        analyzer = dynamic_analyzer
        
        # Perform comprehensive workflow analysis
        analysis_result = analyzer.analyze_workflow(flow_data)
        
        logger.info(f"Dynamic analysis complete - Found {len(analysis_result.node_types)} node types")
        logger.info(f"Environment variables: {len(analysis_result.environment_variables)} total")
        logger.info(f"Package dependencies: {len(analysis_result.package_dependencies)} packages")
        
        # Convert DynamicAnalysisResult to WorkflowDependencies format
        required_env_vars = []
        optional_env_vars = []
        
        # Process environment variables by required status
        for env_var in analysis_result.environment_variables:
            if env_var.required:
                required_env_vars.append(EnvironmentVariable(
                    name=env_var.name,
                    description=env_var.description,
                    example=env_var.example or "",
                    required=True,
                    node_type=env_var.node_type or "Dynamic"
                ))
            else:
                optional_env_vars.append(EnvironmentVariable(
                    name=env_var.name,
                    description=env_var.description,
                    example=env_var.example or "",
                    default=str(env_var.default) if env_var.default is not None else "",
                    required=False,
                    node_type=env_var.node_type or "Dynamic"
                ))
        
        # Define standard API endpoints
        api_endpoints = [
            f"POST /{API_START}/workflow/execute",
            f"GET /{API_START}/workflow/status/{{execution_id}}",
            f"GET /{API_START}/workflow/result/{{execution_id}}",
            f"GET /{API_START}/health",
            f"GET /{API_START}/workflow/info",
            f"GET /{API_START}/workflow/external/info",
            f"POST /{API_START}/workflow/external/ping",
            f"GET /{API_START}/workflow/external/metrics"
        ]
        
        logger.info(f" Dynamic analysis summary:")
        logger.info(f"   • Node types: {', '.join(analysis_result.node_types)}")
        logger.info(f"   • Critical credentials detected: {len([v for v in analysis_result.environment_variables if v.security_level in ['critical', 'high']])}")
        logger.info(f"   • Package dependencies: {len(analysis_result.package_dependencies)}")
        
        return WorkflowDependencies(
            workflow_id="temp_id",
            nodes=analysis_result.node_types,
            required_env_vars=required_env_vars,
            optional_env_vars=optional_env_vars,
            python_packages=[f"{pkg.name}{pkg.version}" for pkg in analysis_result.package_dependencies],
            api_endpoints=api_endpoints
        )
        
    except Exception as e:
        logger.error(f" Dynamic workflow analysis failed: {e}", exc_info=True)
        logger.warning(" Falling back to legacy static analysis")
        
        # Fallback to simplified static analysis for safety
        return _fallback_static_analysis(flow_data)

def _fallback_static_analysis(flow_data: Dict[str, Any]) -> WorkflowDependencies:
    """Fallback static analysis for error conditions."""
    logger.info(" Executing fallback static analysis")
    
    nodes = flow_data.get("nodes", [])
    node_types = list(set(node.get("type", "") for node in nodes if node.get("type")))
    
    # Basic required environment variables
    required_env_vars = [
        EnvironmentVariable(
            name="DATABASE_URL",
            description="Database connection URL for workflow execution",
            example="postgresql://user:password@localhost:5432/workflow_db",
            required=True,
            node_type="System"
        )
    ]
    
    # Basic optional environment variables
    optional_env_vars = [
        EnvironmentVariable(
            name="LANGCHAIN_API_KEY",
            description="LangSmith API key for monitoring (optional)",
            example="lsv2_sk_abc123...",
            default="",
            required=False,
            node_type="Monitoring"
        )
    ]
    
    # Basic package dependencies
    python_packages = [
        "fastapi>=0.104.0",
        "uvicorn[standard]>=0.24.0",
        "sqlalchemy>=2.0.0",
        "asyncpg>=0.28.0",
        "pydantic>=2.5.0",
        "langchain>=0.1.0",
        "langchain-core>=0.1.0"
    ]
    
    # API endpoints
    api_endpoints = [
        f"POST /{API_START}/workflow/execute",
        f"GET /{API_START}/workflow/status/{{execution_id}}",
        f"GET /{API_START}/health",
        f"GET /{API_START}/workflow/info"
    ]
    
    return WorkflowDependencies(
        workflow_id="temp_id",
        nodes=node_types,
        required_env_vars=required_env_vars,
        optional_env_vars=optional_env_vars,
        python_packages=python_packages,
        api_endpoints=api_endpoints
    )

def get_required_env_vars_for_workflow(dependencies: WorkflowDependencies) -> Dict[str, Any]:
    """Get required environment variables for workflow."""
    return {
        "required": [
            {
                "name": var.name,
                "description": var.description,
                "example": var.example,
                "node": var.node_type
            }
            for var in dependencies.required_env_vars
        ],
        "optional": [
            {
                "name": var.name,
                "description": var.description,
                "default": var.default,
                "node": var.node_type
            }
            for var in dependencies.optional_env_vars
        ]
    }

def validate_env_variables(dependencies: WorkflowDependencies, env_vars: Dict[str, str]) -> Dict[str, Any]:
    """Validate provided environment variables against requirements."""
    errors = []
    warnings = []
    
    # Check required variables
    for var in dependencies.required_env_vars:
        if var.name not in env_vars or not env_vars[var.name].strip():
            errors.append(f"Required environment variable '{var.name}' is missing or empty")
    
    # Check for potentially invalid values
    for var_name, var_value in env_vars.items():
        if var_name == "OPENAI_API_KEY" and not var_value.startswith("sk-"):
            warnings.append(f"OpenAI API key format may be invalid (should start with 'sk-')")
        elif var_name == "TAVILY_API_KEY" and not var_value.startswith("tvly-"):
            warnings.append(f"Tavily API key format may be invalid (should start with 'tvly-')")
        elif var_name == "DATABASE_URL" and not var_value.startswith(("postgresql://", "mysql://", "sqlite://")):
            warnings.append(f"Database URL format may be invalid")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }
=======
>>>>>>> serialization_fixes
