import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    session_id: Mapped[str] = mapped_column(
        String, ForeignKey("inspection_sessions.id"), nullable=False
    )
    image_path: Mapped[str] = mapped_column(String(500), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(50), default="pending", nullable=False
    )

    session: Mapped["InspectionSession"] = relationship(back_populates="scans")
    extracted_fields: Mapped[list["ExtractedField"]] = relationship(
        back_populates="scan"
    )
    violations: Mapped[list["Violation"]] = relationship(back_populates="scan")
