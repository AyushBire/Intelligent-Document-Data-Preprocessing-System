import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.pipeline_service import get_job

router = APIRouter()
logger = logging.getLogger("ws")

# job_id → list of connected WebSockets
_connections: dict[str, list[WebSocket]] = {}


async def broadcast_job(job_id: str, data: dict) -> None:
    sockets = _connections.get(job_id, [])
    dead = []
    for ws in sockets:
        try:
            await ws.send_json(data)
        except Exception:
            dead.append(ws)
    for ws in dead:
        sockets.remove(ws)


@router.websocket("/ws/jobs/{job_id}")
async def job_progress(websocket: WebSocket, job_id: str):
    await websocket.accept()
    _connections.setdefault(job_id, []).append(websocket)
    logger.info(f"WS connected: job={job_id}")

    try:
        # Send current state immediately on connect
        job = get_job(job_id)
        if job:
            await websocket.send_json(job.model_dump())

        # Keep alive — client closes when done
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        logger.info(f"WS disconnected: job={job_id}")
    finally:
        conns = _connections.get(job_id, [])
        if websocket in conns:
            conns.remove(websocket)
        if not conns:
            _connections.pop(job_id, None)