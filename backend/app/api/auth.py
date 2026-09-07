from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_officer
from app.core.security import create_access_token, verify_password
from app.db.base import get_db
from app.db.models.officer import Officer
from app.schemas.auth import LoginRequest, OfficerResponse, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(
    login_data: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    """Authenticate an enforcement officer via @nic.in email and password."""
    email = login_data.email.strip().lower()
    officer = db.query(Officer).filter(Officer.email.ilike(email)).first()

    if not officer or not verify_password(login_data.password, officer.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        subject=officer.id,
        extra_claims={
            "email": officer.email,
            "name": officer.name,
        },
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        officer_id=officer.id,
        name=officer.name,
        email=officer.email,
        badge_number=officer.badge_number,
        jurisdiction=officer.jurisdiction,
    )


@router.get("/me", response_model=OfficerResponse)
def get_current_officer_profile(
    current_officer: Annotated[Officer, Depends(get_current_officer)],
) -> OfficerResponse:
    """Return profile information of the currently authenticated officer."""
    return current_officer
