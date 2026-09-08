import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_officer
from app.db.base import get_db
from app.db.models.extracted_field import ExtractedField
from app.db.models.inspection_session import InspectionSession
from app.db.models.officer import Officer
from app.db.models.scan import Scan
from app.db.models.violation import Violation
from app.rules.registry import get_rule, run_all_rules
import app.rules  # noqa: F401 — triggers @register_rule decorators
from app.schemas.scan import ComplianceReport, RuleResultResponse, ScanResponse
from app.services.ocr import extract_text
from app.services.parser import classify_fields
from app.services.preprocessing import preprocess_image

logger = logging.getLogger(__name__)

router = APIRouter(tags=["scans"])

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def parse_captured_at(captured_at: str | None) -> datetime:
    """Use the client capture time for queued scans while accepting normal uploads."""
    if not captured_at:
        return datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="captured_at must be an ISO 8601 timestamp.",
        ) from exc
    if parsed.tzinfo is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="captured_at must include a timezone.",
        )
    return parsed.astimezone(timezone.utc)


@router.post(
    "/sessions/{session_id}/scans",
    response_model=ScanResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_scan(
    session_id: str,
    file: UploadFile = File(...),
    captured_at: str | None = Form(default=None),
    current_officer: Annotated[Officer, Depends(get_current_officer)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> ScanResponse:
    """Upload a label photo, preprocess, OCR, classify fields, and run compliance checks."""
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

    # Read image bytes
    contents = await file.read()
    if not contents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    # Save to disk
    scan_id = str(uuid.uuid4())
    extension = Path(file.filename or "image.jpg").suffix or ".jpg"
    file_path = UPLOAD_DIR / f"{scan_id}{extension}"
    with open(file_path, "wb") as f:
        f.write(contents)

    scan = Scan(
        id=scan_id,
        session_id=session.id,
        image_path=str(file_path),
        captured_at=parse_captured_at(captured_at),
        status="processing",
    )
    db.add(scan)
    db.commit()

    classified_fields_dict: dict[str, str | None] = {}
    compliance_report: ComplianceReport | None = None

    # Run preprocessing + OCR + classification + rule engine
    try:
        # Step 1: Preprocess image
        processed_img = preprocess_image(contents)

        # Step 2: OCR extraction
        ocr_blocks = extract_text(processed_img)

        # Store raw OCR blocks
        for block in ocr_blocks:
            field = ExtractedField(
                scan_id=scan.id,
                field_type="raw_ocr",
                raw_text=block.text,
                confidence_score=block.confidence,
                bounding_box=block.bounding_box_json(),
            )
            db.add(field)

        # Step 3: Classify fields from OCR blocks
        classified_fields_dict = classify_fields(ocr_blocks)

        # Store classified fields as ExtractedField records
        for field_name, field_value in classified_fields_dict.items():
            if field_value is not None:
                classified_ef = ExtractedField(
                    scan_id=scan.id,
                    field_type=field_name,
                    raw_text=field_value,
                    confidence_score=None,
                )
                db.add(classified_ef)

        # Step 4: Run rule engine
        rule_results = run_all_rules(classified_fields_dict)

        # Build compliance report
        passed_count = sum(1 for r in rule_results if r.passed)
        failed_count = sum(1 for r in rule_results if not r.passed)
        compliance_report = ComplianceReport(
            total_rules=len(rule_results),
            passed=passed_count,
            failed=failed_count,
            results=[
                RuleResultResponse(
                    passed=r.passed,
                    rule_id=r.rule_id,
                    description=r.description,
                    citation=r.citation,
                    extracted_value=r.extracted_value,
                    reason=r.reason,
                )
                for r in rule_results
            ],
        )

        # Step 5: Persist violations for failed rules
        for r in rule_results:
            if not r.passed:
                violation = Violation(
                    scan_id=scan.id,
                    rule_id=r.rule_id,
                    # Product triage level; it does not purport to be a legal penalty.
                    severity=get_rule(r.rule_id).severity if get_rule(r.rule_id) else "major",
                    citation=r.citation,
                    reason=r.reason or f"Rule {r.rule_id} check failed.",
                )
                db.add(violation)

        scan.status = "completed"
    except Exception as exc:
        logger.error("Scan processing pipeline failed for %s: %s", scan.id, exc, exc_info=True)
        scan.status = "failed"

    db.commit()
    db.refresh(scan)
    return ScanResponse.from_scan_orm(scan, classified_fields_dict, compliance_report)


@router.get("/scans/{scan_id}", response_model=ScanResponse)
def get_scan(
    scan_id: str,
    current_officer: Annotated[Officer, Depends(get_current_officer)],
    db: Annotated[Session, Depends(get_db)],
) -> ScanResponse:
    """Retrieve scan details, extracted fields, and raw OCR blocks."""
    scan = (
        db.query(Scan)
        .join(InspectionSession)
        .filter(
            Scan.id == scan_id,
            InspectionSession.officer_id == current_officer.id,
        )
        .first()
    )
    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan '{scan_id}' not found.",
        )
    return ScanResponse.from_scan_orm(scan)


@router.get("/sessions/{session_id}/scans", response_model=list[ScanResponse])
def list_session_scans(
    session_id: str,
    current_officer: Annotated[Officer, Depends(get_current_officer)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ScanResponse]:
    """List all scans belonging to an inspection session."""
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

    scans = (
        db.query(Scan)
        .filter(Scan.session_id == session_id)
        .order_by(Scan.captured_at.desc())
        .all()
    )
    return [ScanResponse.from_scan_orm(s) for s in scans]
