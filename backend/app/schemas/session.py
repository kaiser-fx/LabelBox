from datetime import datetime

from pydantic import BaseModel


class SessionCreate(BaseModel):
    store_name: str
    location: str | None = None


class SessionResponse(BaseModel):
    id: str
    officer_id: str
    store_name: str
    location: str | None
    started_at: datetime

    model_config = {"from_attributes": True}


class SessionReportScan(BaseModel):
    """A compact, reopenable scan entry included in a session report."""

    id: str
    captured_at: datetime
    status: str
    violation_count: int
    is_compliant: bool


class SessionReport(BaseModel):
    """Aggregate compliance state for one inspection session."""

    session: SessionResponse
    total_scans: int
    completed_scans: int
    processing_scans: int
    failed_scans: int
    compliant_scans: int
    scans_with_violations: int
    total_violations: int
    violations_by_rule: dict[str, int]
    scans: list[SessionReportScan]
