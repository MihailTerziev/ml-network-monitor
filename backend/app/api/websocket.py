from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/ws", tags=["websocket"])


@router.websocket("/monitoring/{session_id}")
async def monitoring_socket(websocket: WebSocket, session_id: str):
    await websocket.accept()
    try:
        while True:
            await websocket.send_json({
                "session_id": session_id,
                "event": "heartbeat",
                "status": "connected",
            })
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
