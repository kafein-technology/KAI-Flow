import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.services.node_registry_service import NodeRegistryService
from app.api.schemas import (
    NodeRegistryCreate,
    NodeRegistryUpdate,
    NodeRegistryResponse,
    NodeRegistryListResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()
node_registry_service = NodeRegistryService()


@router.get("", response_model=NodeRegistryListResponse)
async def get_node_registry_list(
    db: AsyncSession = Depends(get_db_session),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    category: Optional[str] = Query(None, description="Filter by category"),
    active_only: bool = Query(False, description="Show only active nodes"),
    search: Optional[str] = Query(
        None, description="Search in node_type, node_class, or category"
    ),
):
    """
    Get a list of node registry entries with optional filtering.
    """
    try:
        if search:
            nodes = await node_registry_service.search_nodes(db, search, skip, limit)
        elif category:
            nodes = await node_registry_service.get_by_category(
                db, category, skip, limit
            )
        elif active_only:
            nodes = await node_registry_service.get_active_nodes(db, skip, limit)
        else:
            nodes = await node_registry_service.get_all(db, skip=skip, limit=limit)

        # Convert to response format
        node_responses = [
            NodeRegistryResponse(
                id=str(node.id),
                node_type=node.node_type,
                node_class=node.node_class,
                category=node.category,
                version=node.version,
                schema_definition=node.schema_definition,
                ui_schema=node.ui_schema,
                is_active=node.is_active,
                created_at=node.created_at.isoformat() if node.created_at else None,
            )
            for node in nodes
        ]

        return NodeRegistryListResponse(
            nodes=node_responses,
            total=len(node_responses),  # TODO: Add proper count query
            page=skip // limit + 1,
            size=limit,
        )
    except Exception as e:
        logger.error(f"Error getting node registry list: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{node_type}", response_model=NodeRegistryResponse)
async def get_node_registry_by_type(
    node_type: str, db: AsyncSession = Depends(get_db_session)
):
    """
    Get detailed information about a specific node type.
    """
    try:
        node = await node_registry_service.get_by_node_type(db, node_type)
        if not node:
            raise HTTPException(
                status_code=404, detail=f"Node type '{node_type}' not found"
            )

        return NodeRegistryResponse(
            id=str(node.id),
            node_type=node.node_type,
            node_class=node.node_class,
            category=node.category,
            version=node.version,
            schema_definition=node.schema_definition,
            ui_schema=node.ui_schema,
            is_active=node.is_active,
            created_at=node.created_at.isoformat() if node.created_at else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting node registry by type {node_type}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("", response_model=NodeRegistryResponse)
async def create_node_registry(
    node_data: NodeRegistryCreate, db: AsyncSession = Depends(get_db_session)
):
    """
    Create a new node registry entry.
    """
    try:
        node = await node_registry_service.create_node_registry(db, node_data)

        return NodeRegistryResponse(
            id=str(node.id),
            node_type=node.node_type,
            node_class=node.node_class,
            category=node.category,
            version=node.version,
            schema_definition=node.schema_definition,
            ui_schema=node.ui_schema,
            is_active=node.is_active,
            created_at=node.created_at.isoformat() if node.created_at else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating node registry: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{node_type}", response_model=NodeRegistryResponse)
async def update_node_registry(
    node_type: str,
    node_data: NodeRegistryUpdate,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Update an existing node registry entry.
    """
    try:
        node = await node_registry_service.update_node_registry(
            db, node_type, node_data
        )
        if not node:
            raise HTTPException(
                status_code=404, detail=f"Node type '{node_type}' not found"
            )

        return NodeRegistryResponse(
            id=str(node.id),
            node_type=node.node_type,
            node_class=node.node_class,
            category=node.category,
            version=node.version,
            schema_definition=node.schema_definition,
            ui_schema=node.ui_schema,
            is_active=node.is_active,
            created_at=node.created_at.isoformat() if node.created_at else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating node registry {node_type}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{node_type}")
async def delete_node_registry(
    node_type: str, db: AsyncSession = Depends(get_db_session)
):
    """
    Delete a node registry entry.
    """
    try:
        node = await node_registry_service.delete_node_registry(db, node_type)
        if not node:
            raise HTTPException(
                status_code=404, detail=f"Node type '{node_type}' not found"
            )

        return {"message": f"Node type '{node_type}' deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting node registry {node_type}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{node_type}/toggle")
async def toggle_node_active_status(
    node_type: str, db: AsyncSession = Depends(get_db_session)
):
    """
    Toggle the active status of a node registry entry.
    """
    try:
        node = await node_registry_service.toggle_active_status(db, node_type)
        if not node:
            raise HTTPException(
                status_code=404, detail=f"Node type '{node_type}' not found"
            )

        return {
            "message": f"Node type '{node_type}' {'activated' if node.is_active else 'deactivated'} successfully",
            "is_active": node.is_active,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling node status {node_type}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stats/summary")
async def get_node_registry_statistics(db: AsyncSession = Depends(get_db_session)):
    """
    Get statistics about node registry entries.
    """
    try:
        stats = await node_registry_service.get_statistics(db)
        return stats
    except Exception as e:
        logger.error(f"Error getting node registry statistics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/categories/list")
async def get_node_categories(db: AsyncSession = Depends(get_db_session)):
    """
    Get a list of all available node categories.
    """
    try:
        # Get all nodes and extract unique categories
        nodes = await node_registry_service.get_all(db, skip=0, limit=1000)
        categories = list(set(node.category for node in nodes))

        return {"categories": sorted(categories), "total_categories": len(categories)}
    except Exception as e:
        logger.error(f"Error getting node categories: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
