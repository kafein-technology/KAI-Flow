# scripts/__init__.py
"""
KAI-Fusion CLI Scripts
======================

Command-line utilities for workflow management.

Usage:
    # Export workflows
    python -m scripts.export_workflows --ids "uuid1,uuid2" --output ./bundle
    python -m scripts.export_workflows --user-email "admin@example.com" --output ./bundle
    
    # Import workflows  
    python -m scripts.import_workflows --config ./bundle/workflows_config.yaml
    python -m scripts.import_workflows --config ./bundle/workflows_config.yaml --dry-run
"""
