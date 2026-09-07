from collections import Counter

from app.db.models.inspection_session import InspectionSession
from app.schemas.session import SessionReport, SessionReportScan, SessionResponse


def build_session_report(session: InspectionSession) -> SessionReport:
    """Build a deterministic aggregate from scans already loaded for a session."""
    scans = sorted(session.scans, key=lambda scan: scan.captured_at, reverse=True)
    completed_scans = sum(scan.status == "completed" for scan in scans)
    processing_scans = sum(scan.status in {"pending", "processing"} for scan in scans)
    failed_scans = sum(scan.status == "failed" for scan in scans)
    violation_counts = Counter(
        violation.rule_id for scan in scans for violation in scan.violations
    )
    scans_with_violations = sum(bool(scan.violations) for scan in scans)
    compliant_scans = sum(
        scan.status == "completed" and not scan.violations for scan in scans
    )

    return SessionReport(
        session=SessionResponse.model_validate(session),
        total_scans=len(scans),
        completed_scans=completed_scans,
        processing_scans=processing_scans,
        failed_scans=failed_scans,
        compliant_scans=compliant_scans,
        scans_with_violations=scans_with_violations,
        total_violations=sum(violation_counts.values()),
        violations_by_rule=dict(sorted(violation_counts.items())),
        scans=[
            SessionReportScan(
                id=scan.id,
                captured_at=scan.captured_at,
                status=scan.status,
                violation_count=len(scan.violations),
                is_compliant=scan.status == "completed" and not scan.violations,
            )
            for scan in scans
        ],
    )
