import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class InspectionSession(Base):
    __tablename__ = "inspection_sessions"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    officer_id: Mapped[str] = mapped_column(
        String, ForeignKey("officers.id"), nullable=False
    )
    store_name: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(500), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )


    officer: Mapped["Officer"] = relationship(back_populates="sessions")
    scans: Mapped[list["Scan"]] = relationship(back_populates="session")
