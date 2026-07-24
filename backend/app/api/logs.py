import asyncio
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.core.enhanced_logging import log_history, log_subscribers

router = APIRouter()

@router.get("/stream")
async def stream_logs():
    """
    Stream real-time backend logs using Server-Sent Events (SSE).
    First yields the historical logs from the in-memory buffer,
    then streams new logs as they are produced.
    """
    queue = asyncio.Queue(maxsize=1000)
    loop = asyncio.get_running_loop()
    
    # Register this subscriber
    subscriber = (queue, loop)
    log_subscribers.add(subscriber)
    
    def format_sse(msg: str) -> str:
        # Split by newline and format each line as "data: <line>\n" for SSE spec compliance
        lines = msg.splitlines()
        sse_msg = "".join(f"data: {line}\n" for line in lines)
        return f"{sse_msg}\n"
    
    async def log_generator():
        try:
            # 1. Send all currently cached history logs immediately
            history_copy = list(log_history)
            for msg in history_copy:
                yield format_sse(msg)
            
            # 2. Stream new logs
            while True:
                try:
                    # Retrieve log message from queue with a 30s timeout to send a keep-alive ping
                    msg = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield format_sse(msg)
                except asyncio.TimeoutError:
                    # Keep-alive comment for SSE
                    yield ": ping\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            # Clean up when connection closes
            log_subscribers.discard(subscriber)

    return StreamingResponse(
        log_generator(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )
