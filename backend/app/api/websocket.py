import asyncio
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError

from app.broker.zeek_consumer import event_hub
from app.database import SessionLocal
from app.models.monitoring_session import MonitoringSession
from app.models.user import User
from app.services.auth_service import decode_access_token

router = APIRouter(prefix="/ws", tags=["websocket"])


@router.websocket("/monitoring/{session_id}")
async def monitoring_socket(websocket: WebSocket, session_id: str):
    await websocket.accept()
    try:
        auth_message = await asyncio.wait_for(websocket.receive_json(), timeout=5)
        token = auth_message.get("token", "") if isinstance(auth_message, dict) else ""
    except (WebSocketDisconnect, asyncio.TimeoutError):
        await websocket.close(code=4401, reason="Authentication required")
        return
    try:
        user_id = UUID(decode_access_token(token)["sub"])
        session_uuid = UUID(session_id)
    except (JWTError, KeyError, ValueError, TypeError):
        await websocket.close(code=4401, reason="Authentication required")
        return

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
        session = (
            db.query(MonitoringSession)
            .filter(MonitoringSession.id == session_uuid, MonitoringSession.user_id == user_id)
            .first()
        )
        if user is None or session is None:
            await websocket.close(code=4404, reason="Monitoring session not found")
            return
    finally:
        db.close()

    queue = event_hub.subscribe(session_id)
    try:
        while True:
            event = await queue.get()
            await websocket.send_json(event)
    except WebSocketDisconnect:
        pass
    finally:
        event_hub.unsubscribe(session_id, queue)
