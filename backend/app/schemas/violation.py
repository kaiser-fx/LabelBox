from pydantic import BaseModel


class ViolationResponse(BaseModel):
    rule_id: str
    description: str
    citation: str
    severity: str = "major"
    extracted_value: str | None = None
    reason: str | None = None

    model_config = {"from_attributes": True}


class ComplianceReport(BaseModel):
    """Full compliance report for a scan — all rules checked."""
    total_rules: int
    passed: int
    failed: int
    results: list["RuleResultResponse"]


class RuleResultResponse(BaseModel):
    passed: bool
    rule_id: str
    description: str
    citation: str
    extracted_value: str | None = None
    reason: str | None = None
