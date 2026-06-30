from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional
import logging
import asyncio

from app.core.database import get_db_session
from app.nodes.triggers.timer_start_node import active_timers
from app.models.workflow import Workflow
from app.core.engine import get_engine

logger = logging.getLogger(__name__)
router = APIRouter(tags=["timers"])

async def bootstrap_timer_node(timer_id: str, db: AsyncSession) -> bool:
    """
    Search database for a workflow containing a TimerStartNode with matching ID or timer_id,
    and build the engine to instantiate it in memory.
    """
    try:
        result = await db.execute(select(Workflow))
        workflows = result.scalars().all()
        for wf in workflows:
            flow_data = wf.flow_data or {}
            nodes = flow_data.get("nodes", [])
            for node in nodes:
                node_id = node.get("id")
                node_type = node.get("type")
                node_data = node.get("data", {})
                node_timer_id = node_data.get("timer_id")
                
                # Check both node ID and node's timer_id
                if node_type in ("TimerStartNode", "TimerStart") and (node_id == timer_id or node_timer_id == timer_id):
                    logger.info(f"Bootstrapping timer node {timer_id} from workflow {wf.id}")
                    engine = get_engine()
                    user_context = {
                        "session_id": f"bootstrap_{timer_id}",
                        "user_id": str(wf.user_id),
                        "owner_id": str(wf.user_id),
                        "workflow_id": str(wf.id)
                    }
                    # Build graph to instantiate nodes in memory
                    engine.build(flow_data=flow_data, user_context=user_context)
                    
                    # Manually set workflow_id and user_id on newly instantiated node
                    for info in active_timers.values():
                        inst = info.get("node_instance")
                        if inst and (getattr(inst, "node_id", None) == timer_id or getattr(inst, "timer_id", None) == timer_id):
                            inst.workflow_id = str(wf.id)
                            inst.user_id = str(wf.user_id)
                            logger.info(f"Set workflow_id and user_id on newly bootstrapped node {timer_id}")
                            break
                    return True
        return False
    except Exception as e:
        logger.error(f"Error bootstrapping timer node {timer_id}: {e}", exc_info=True)
        return False

def find_node_by_timer_or_node_id(timer_id: str) -> Optional[Any]:
    """Find the TimerStartNode instance by either timer_id or node_id in active_timers."""
    # 1. Try direct lookup by timer_id
    if timer_id in active_timers:
        return active_timers[timer_id]["node_instance"]
    
    # 2. Try lookup by node_id
    for info in active_timers.values():
        node = info.get("node_instance")
        if node and getattr(node, "node_id", None) == timer_id:
            return node
            
    return None

async def ensure_node_context(node: Any, db: AsyncSession) -> None:
    """Ensure that workflow_id and user_id are set on the node instance by querying DB if needed."""
    if not getattr(node, "workflow_id", None) or not getattr(node, "user_id", None):
        timer_id = getattr(node, "node_id", None) or getattr(node, "timer_id", None)
        result = await db.execute(select(Workflow))
        workflows = result.scalars().all()
        for wf in workflows:
            flow_data = wf.flow_data or {}
            nodes = flow_data.get("nodes", [])
            for n in nodes:
                n_id = n.get("id")
                n_data = n.get("data", {})
                n_timer_id = n_data.get("timer_id")
                if n_id == timer_id or n_timer_id == timer_id:
                    node.workflow_id = str(wf.id)
                    node.user_id = str(wf.user_id)
                    logger.info(f"Ensured workflow_id={node.workflow_id} and user_id={node.user_id} on node {timer_id}")
                    return

@router.get("/{timer_id}/status")
async def get_timer_status(timer_id: str, db: AsyncSession = Depends(get_db_session)):
    node = find_node_by_timer_or_node_id(timer_id)
    
    if not node:
        # Try bootstrapping from DB
        success = await bootstrap_timer_node(timer_id, db)
        if success:
            node = find_node_by_timer_or_node_id(timer_id)
            
    if not node:
        # Default inactive status to prevent UI crashes
        return {
            "timer_id": timer_id,
            "is_active": False,
            "status": "stopped",
            "next_execution": None,
            "last_execution": None,
            "execution_count": 0
        }
        
    await ensure_node_context(node, db)
    status_data = node.get_timer_status()
    stats = status_data.get("timer_stats", {})
    return {
        "timer_id": status_data.get("timer_id"),
        "is_active": status_data.get("is_active", False),
        "status": stats.get("status", "stopped"),
        "next_execution": stats.get("next_execution"),
        "last_execution": stats.get("last_execution"),
        "execution_count": stats.get("execution_count", 0)
    }

@router.post("/{timer_id}/start")
async def start_timer(timer_id: str, db: AsyncSession = Depends(get_db_session)):
    node = find_node_by_timer_or_node_id(timer_id)
    
    if not node:
        # Try bootstrapping from DB
        success = await bootstrap_timer_node(timer_id, db)
        if success:
            node = find_node_by_timer_or_node_id(timer_id)
            
    if not node:
        raise HTTPException(status_code=404, detail=f"Timer node {timer_id} not found")
        
    await ensure_node_context(node, db)
    return node.start_timer()

@router.post("/{timer_id}/stop")
async def stop_timer(timer_id: str, db: AsyncSession = Depends(get_db_session)):
    node = find_node_by_timer_or_node_id(timer_id)
    
    if not node:
        # Try bootstrapping from DB
        success = await bootstrap_timer_node(timer_id, db)
        if success:
            node = find_node_by_timer_or_node_id(timer_id)
            
    if not node:
        raise HTTPException(status_code=404, detail=f"Timer node {timer_id} not found")
        
    await ensure_node_context(node, db)
    return node.stop_timer()

@router.post("/{timer_id}/trigger")
async def trigger_timer(timer_id: str, db: AsyncSession = Depends(get_db_session)):
    node = find_node_by_timer_or_node_id(timer_id)
    
    if not node:
        # Try bootstrapping from DB
        success = await bootstrap_timer_node(timer_id, db)
        if success:
            node = find_node_by_timer_or_node_id(timer_id)
            
    if not node:
        raise HTTPException(status_code=404, detail=f"Timer node {timer_id} not found")
        
    await ensure_node_context(node, db)
    return await node.trigger_now()

# Global dictionary to track active UI stream subscribers for each timer
timer_subscribers: Dict[str, list[asyncio.Queue]] = {}

@router.get("/{timer_id}/stream")
async def stream_timer(timer_id: str):
    """Stream execution events for a specific timer trigger to the canvas UI."""
    from fastapi.responses import StreamingResponse
    from datetime import datetime, timezone
    from app.core.json_utils import make_json_serializable
    import asyncio
    import json
    
    async def event_stream():
        # Setup queue for this subscriber (using standard MAX_QUEUE_LENGTH style queue size)
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        timer_subscribers.setdefault(timer_id, []).append(queue)
        logger.info(f"UI client subscribed to stream for timer {timer_id}")
        
        try:
            # Send initial connected message
            yield f"data: {json.dumps({'type': 'connected', 'timer_id': timer_id, 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"
            
            while True:
                try:
                    # Keepalive ping or get next queued event
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    serializable_event = make_json_serializable(event)
                    yield f"data: {json.dumps(serializable_event)}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive ping
                    yield f"data: {json.dumps({'type': 'ping', 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"
        except asyncio.CancelledError:
            logger.info(f"UI client unsubscribed from stream for timer {timer_id}")
        finally:
            # Cleanup subscriber
            if timer_id in timer_subscribers and queue in timer_subscribers[timer_id]:
                timer_subscribers[timer_id].remove(queue)
                
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

