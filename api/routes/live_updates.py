"""
Live Updates API - Server-Sent Events endpoint for real-time scraper notifications.
"""

import logging
import asyncio
import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/live", tags=["live-updates"])


@router.get("/updates")
async def stream_live_updates():
    """
    Server-Sent Events endpoint. Clients connect here and listen for scraper completion events.
    
    Returns: Event stream with scraper notifications.
    
    Example client:
    ```javascript
    const eventSource = new EventSource('/api/live/updates');
    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('Scraper update:', data);
    };
    ```
    """
    from api.services.live_updates import register_client_queue, unregister_client_queue
    
    queue: asyncio.Queue = asyncio.Queue(maxsize=50)
    
    # Register this client
    await register_client_queue(queue)
    logger.info("[LIVE-UPDATES-ENDPOINT] Client connected to SSE stream")
    
    async def event_generator():
        """Generate SSE events from queue."""
        try:
            # Send initial connection message
            yield f"data: {json.dumps({'type': 'connected', 'message': 'Live updates connected'})}\n\n"
            
            # Stream events as they arrive
            while True:
                try:
                    # Wait for event with timeout to allow cleanup
                    event = await asyncio.wait_for(queue.get(), timeout=60.0)
                    # Send as SSE
                    yield f"data: {event.to_json()}\n\n"
                except asyncio.TimeoutError:
                    # Send keep-alive comment every 60s
                    yield f": connection keep-alive\n\n"
                except asyncio.CancelledError:
                    break
        except Exception as e:
            logger.error(f"[LIVE-UPDATES-ENDPOINT] Event generator error: {e}")
        finally:
            # Unregister on disconnect
            await unregister_client_queue(queue)
            logger.info("[LIVE-UPDATES-ENDPOINT] Client disconnected from SSE stream")
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.get("/status")
async def get_live_updates_status():
    """Get status of live updates system."""
    from api.services.live_updates import get_connected_client_count
    
    return {
        "status": "active",
        "connected_clients": get_connected_client_count(),
    }
