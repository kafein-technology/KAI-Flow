from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_

from app.models.node_registry import NodeRegistry
from app.services.base import BaseService
from app.api.schemas import NodeRegistryCreate, NodeRegistryUpdate


class NodeRegistryService(BaseService[NodeRegistry]):
    def __init__(self):
        super().__init__(NodeRegistry)

    async def get_by_node_type(self, db: AsyncSession, node_type: str) -> Optional[NodeRegistry]:
        """
        Get a node registry entry by node_type.
        """
        result = await db.execute(
            select(NodeRegistry).filter(NodeRegistry.node_type == node_type)
        )
        return result.scalars().first()

    async def get_by_category(self, db: AsyncSession, category: str, skip: int = 0, limit: int = 100) -> List[NodeRegistry]:
        """
        Get all node registry entries by category.
        """
        result = await db.execute(
            select(NodeRegistry)
            .filter(NodeRegistry.category == category)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_active_nodes(self, db: AsyncSession, skip: int = 0, limit: int = 100) -> List[NodeRegistry]:
        """
        Get all active node registry entries.
        """
        result = await db.execute(
            select(NodeRegistry)
            .filter(NodeRegistry.is_active == True)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def create_node_registry(self, db: AsyncSession, obj_in: NodeRegistryCreate) -> NodeRegistry:
        """
        Create a new node registry entry.
        """
        # Check if node_type already exists
        existing = await self.get_by_node_type(db, obj_in.node_type)
        if existing:
            raise ValueError(f"Node type '{obj_in.node_type}' already exists")
        
        obj_in_data = obj_in.model_dump()
        db_obj = NodeRegistry(**obj_in_data)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update_node_registry(self, db: AsyncSession, node_type: str, obj_in: NodeRegistryUpdate) -> Optional[NodeRegistry]:
        """
        Update a node registry entry by node_type.
        """
        db_obj = await self.get_by_node_type(db, node_type)
        if not db_obj:
            return None

        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def delete_node_registry(
        self, db: AsyncSession, node_type: str
    ) -> Optional[NodeRegistry]:
        """
        Delete a node registry entry by node_type.
        """
        db_obj = await self.get_by_node_type(db, node_type)
        if not db_obj:
            return None

        await db.delete(db_obj)
        await db.commit()
        return db_obj

    async def toggle_active_status(
        self, db: AsyncSession, node_type: str
    ) -> Optional[NodeRegistry]:
        """
        Toggle the active status of a node registry entry.
        """
        db_obj = await self.get_by_node_type(db, node_type)
        if not db_obj:
            return None

        db_obj.is_active = not db_obj.is_active
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def search_nodes(
        self, db: AsyncSession, query: str, skip: int = 0, limit: int = 100
    ) -> List[NodeRegistry]:
        """
        Search node registry entries by node_type, node_class, or category.
        """
        search_filter = (
            NodeRegistry.node_type.ilike(f"%{query}%")
            | NodeRegistry.node_class.ilike(f"%{query}%")
            | NodeRegistry.category.ilike(f"%{query}%")
        )

        result = await db.execute(
            select(NodeRegistry).filter(search_filter).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def get_statistics(self, db: AsyncSession) -> Dict[str, Any]:
        """
        Get statistics about node registry entries.
        """
        from sqlalchemy import func

        # Total count
        total_result = await db.execute(select(func.count(NodeRegistry.id)))
        total = total_result.scalar()

        # Active count
        active_result = await db.execute(
            select(func.count(NodeRegistry.id)).filter(NodeRegistry.is_active == True)
        )
        active = active_result.scalar()

        # Count by category
        category_result = await db.execute(
            select(NodeRegistry.category, func.count(NodeRegistry.id)).group_by(
                NodeRegistry.category
            )
        )
        categories = dict(category_result.all())

        return {
            "total": total,
            "active": active,
            "inactive": total - active,
            "categories": categories,
        }
