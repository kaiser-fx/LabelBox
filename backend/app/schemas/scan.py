import json
from datetime import datetime
from pydantic import BaseModel, Field


class ScanCreate(BaseModel):
    session_id: str
    image_path: str | None = None


class ExtractedFieldResponse(BaseModel):
    id: str | None = None
    field_type: str
    raw_text: str | None
    confidence_score: float | None
    bounding_box: str | None = None

    model_config = {"from_attributes": True}


class OCRBlockResponse(BaseModel):
    text: str
    confidence: float
    bounding_box: list[list[int]] = Field(default_factory=list)


class ViolationResponse(BaseModel):
    rule_id: str
    severity: str
    citation: str
    reason: str

    model_config = {"from_attributes": True}


class RuleResultResponse(BaseModel):
    passed: bool
    rule_id: str
    description: str
    citation: str
    extracted_value: str | None = None
    reason: str | None = None


class ComplianceReport(BaseModel):
    """Full compliance report for a scan — all rules checked."""
    total_rules: int
    passed: int
    failed: int
    results: list[RuleResultResponse]


class ScanResponse(BaseModel):
    id: str
    session_id: str
    image_path: str | None
    captured_at: datetime
    status: str
    extracted_fields: list[ExtractedFieldResponse] = []
    ocr_blocks: list[OCRBlockResponse] = []
    classified_fields: dict[str, str | None] = {}
    compliance_report: ComplianceReport | None = None
    violations: list[ViolationResponse] = []

    model_config = {"from_attributes": True}

    @classmethod
    def from_scan_orm(cls, scan, classified_fields: dict | None = None,
                      compliance_report: ComplianceReport | None = None) -> "ScanResponse":
        blocks: list[OCRBlockResponse] = []
        for f in scan.extracted_fields:
            if f.field_type == "raw_ocr" and f.raw_text:
                bbox: list[list[int]] = []
                if f.bounding_box:
                    try:
                        bbox = json.loads(f.bounding_box)
                    except Exception:
                        bbox = []
                blocks.append(
                    OCRBlockResponse(
                        text=f.raw_text,
                        confidence=f.confidence_score or 0.0,
                        bounding_box=bbox,
                    )
                )

        # Build classified fields from ExtractedField records if not passed directly
        if classified_fields is None:
            classified_fields = {}
            for f in scan.extracted_fields:
                if f.field_type != "raw_ocr" and f.raw_text:
                    classified_fields[f.field_type] = f.raw_text

        # Build violation responses from ORM relationship
        violation_responses = [
            ViolationResponse(
                rule_id=v.rule_id,
                severity=v.severity,
                citation=v.citation,
                reason=v.reason,
            )
            for v in scan.violations
        ]

        return cls(
            id=scan.id,
            session_id=scan.session_id,
            image_path=scan.image_path,
            captured_at=scan.captured_at,
            status=scan.status,
            extracted_fields=[
                ExtractedFieldResponse.model_validate(f) for f in scan.extracted_fields
            ],
            ocr_blocks=blocks,
            classified_fields=classified_fields,
            compliance_report=compliance_report,
            violations=violation_responses,
        )
