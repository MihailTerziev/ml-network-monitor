from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.monitoring_session import MonitoringSession
from app.schemas.monitoring import MonitoringSessionCreate, MonitoringSessionOut, MonitoringSessionUpdate

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


@router.get("/interfaces")
def list_interfaces():
    try:
        import psutil
        return {"interfaces": list(psutil.net_if_addrs().keys())}
    except Exception:
        return {"interfaces": ["eth0", "lo", "wlp2s0", "en0"]}


@router.post("/sessions", response_model=MonitoringSessionOut)
def create_session(
    payload: MonitoringSessionCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    session = MonitoringSession(
        user_id=current_user.id,
        name=payload.name,
        interface=payload.interface,
        packet_capture_limit_bytes=payload.packet_capture_limit_bytes,
        status="stopped",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/sessions", response_model=List[MonitoringSessionOut])
def list_sessions(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return db.query(MonitoringSession).filter(MonitoringSession.user_id == current_user.id).all()


@router.post("/sessions/{session_id}/start")
def start_session(session_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    session = db.query(MonitoringSession).filter(MonitoringSession.id == session_id).first()
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    session.status = "running"
    db.commit()
    return {"status": "running", "session_id": session_id}


@router.post("/sessions/{session_id}/stop")
def stop_session(session_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    session = db.query(MonitoringSession).filter(MonitoringSession.id == session_id).first()
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    session.status = "stopped"
    db.commit()
    return {"status": "stopped", "session_id": session_id}


@router.put("/sessions/{session_id}", response_model=MonitoringSessionOut)
def update_session(
    session_id: str,
    payload: MonitoringSessionUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    session = db.query(MonitoringSession).filter(MonitoringSession.id == session_id).first()
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    if payload.name is not None:
        session.name = payload.name
    if payload.interface is not None:
        session.interface = payload.interface
    if payload.packet_capture_limit_bytes is not None:
        session.packet_capture_limit_bytes = payload.packet_capture_limit_bytes
    db.commit()
    db.refresh(session)
    return session
