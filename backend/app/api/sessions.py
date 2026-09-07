from datetime import datetime, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_officer
from app.db.base import get_db
from app.db.models.inspection_session import InspectionSession
from app.db.models.officer import Officer
from app.db.models.scan import Scan
from app.schemas.session import SessionCreate, SessionReport, SessionResponse
from app.services.session_report import build_session_report

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    session_in: SessionCreate,
    current_officer: Annotated[Officer, Depends(get_current_officer)],
    db: Annotated[Session, Depends(get_db)],
) -> SessionResponse:
    """Start a new inspection session for the logged-in officer."""
    if not session_in.store_name.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Store name cannot be empty.",
        )

    new_session = InspectionSession(
        officer_id=current_officer.id,
        store_name=session_in.store_name.strip(),
        location=session_in.location.strip() if session_in.location else None,
        started_at=datetime.now(timezone.utc),
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session


@router.get("", response_model=list[SessionResponse])
def list_sessions(
    current_officer: Annotated[Officer, Depends(get_current_officer)],
    db: Annotated[Session, Depends(get_db)],
) -> list[SessionResponse]:
    """Retrieve all inspection sessions conducted by the authenticated officer."""
    sessions = (
        db.query(InspectionSession)
        .filter(InspectionSession.officer_id == current_officer.id)
        .order_by(InspectionSession.started_at.desc())
        .all()
    )
    return sessions


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(
    session_id: str,
    current_officer: Annotated[Officer, Depends(get_current_officer)],
    db: Annotated[Session, Depends(get_db)],
) -> SessionResponse:
    """Get details of a specific inspection session by ID."""
    session = (
        db.query(InspectionSession)
        .filter(
            InspectionSession.id == session_id,
            InspectionSession.officer_id == current_officer.id,
        )
        .first()
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inspection session '{session_id}' not found.",
        )

    return session


@router.get("/{session_id}/report", response_model=SessionReport)
def get_session_report(
    session_id: str,
    current_officer: Annotated[Officer, Depends(get_current_officer)],
    db: Annotated[Session, Depends(get_db)],
) -> SessionReport:
    """Return one officer's aggregate session result for the summary screen."""
    session = (
        db.query(InspectionSession)
        .options(
            selectinload(InspectionSession.scans).selectinload(Scan.violations)
        )
        .filter(
            InspectionSession.id == session_id,
            InspectionSession.officer_id == current_officer.id,
        )
        .first()
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inspection session '{session_id}' not found.",
        )
    return build_session_report(session)
