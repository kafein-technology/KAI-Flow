# scripts/__init__.py
"""
KAI-Flow CLI Scripts
======================

Command-line utilities for workflow management.

Usage:
    # Export workflows
    python -m scripts.export_workflows --ids "uuid1,uuid2" --output ./bundle --name my_project
    python -m scripts.export_workflows --user-email "admin@example.com" --output ./bundle --name my_project
    
    # Import workflows  
    python -m scripts.import_workflows --config ./bundle/my_project_workflows_config.yaml
    python -m scripts.import_workflows --config ./bundle/my_project_workflows_config.yaml --dry-run
"""
