# -*- coding: utf-8 -*-
"""Export functionality schemas and Pydantic models."""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class WorkflowExportConfig(BaseModel):
    """Configuration for basic workflow export request."""
    include_credentials: bool = Field(default=False, description="Include credential schemas")
    export_format: str = Field(default="docker", description="Export format (docker, json)")

class EnvironmentVariable(BaseModel):
    """Environment variable definition."""
    name: str
    description: str
    example: Optional[str] = None
    default: Optional[str] = None
    required: bool = True
    node_type: Optional[str] = None

class WorkflowDependencies(BaseModel):
    """Workflow dependencies analysis result."""
    workflow_id: str
    node_types: List[str] = Field(default_factory=list, description="List of node types used")
    external_packages: List[str] = Field(default_factory=list, description="List of external packages")
    nodes: List[str] = Field(default_factory=list, description="List of node IDs")
    required_env_vars: List[EnvironmentVariable] = Field(default_factory=list, description="Required environment variables")
    optional_env_vars: List[EnvironmentVariable] = Field(default_factory=list, description="Optional environment variables")
    python_packages: List[str] = Field(default_factory=list, description="Python packages needed")
    api_endpoints: List[str] = Field(default_factory=list, description="API endpoints used")

class SecurityConfig(BaseModel):
    """Security configuration for exported workflow."""
    allowed_hosts: str = Field(default="*", description="Comma-separated allowed hosts (* for all hosts)")
    api_keys: Optional[str] = Field(default=None, description="Comma-separated API keys")
    require_api_key: bool = Field(default=False, description="Whether to require API key authentication")
    custom_api_keys: Optional[str] = Field(default=None, description="User custom API keys")

class MonitoringConfig(BaseModel):
    """Monitoring configuration for exported workflow."""
    enable_langsmith: bool = Field(default=False, description="Enable LangSmith monitoring")
    langsmith_api_key: Optional[str] = Field(default=None, description="LangSmith API key")
    langsmith_project: Optional[str] = Field(default=None, description="LangSmith project name")

class DockerConfig(BaseModel):
    """Docker configuration for exported workflow."""
    api_port: int = Field(default=8000, description="Internal API port")
    docker_port: int = Field(default=8000, description="External Docker port")
    database_url: Optional[str] = Field(default=None, description="External database URL")

class WorkflowEnvironmentConfig(BaseModel):
    """Complete environment configuration from user."""
    env_vars: Dict[str, str] = Field(default_factory=dict, description="Environment variables")
    security: SecurityConfig = Field(default_factory=SecurityConfig, description="Security settings")
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig, description="Monitoring settings")
    docker: DockerConfig = Field(default_factory=DockerConfig, description="Docker settings")

class ExportPackage(BaseModel):
    """Export package information."""
    download_url: str
    package_size: int
    workflow_id: str
    export_timestamp: str
    ready_to_run: bool
    instructions: str