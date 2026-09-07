import re

from app.rules.registry import RuleResult, register_rule

_CITATION = (
    "Rule 6(1)(f), Legal Metrology (Packaged Commodities) Rules, 2011 — "
    "Every package shall bear the month and year in which the commodity "
    "is manufactured or pre-packed or imported."
)
_DESCRIPTION = "Date of manufacture or packing must be declared on the package"

# Common date patterns on Indian product labels
_DATE_PATTERNS = [
    # MM/YYYY or MM-YYYY
    re.compile(r"\b(0[1-9]|1[0-2])[/\-](19|20)\d{2}\b"),
    # DD/MM/YYYY or DD-MM-YYYY
    re.compile(r"\b(0[1-9]|[12]\d|3[01])[/\-](0[1-9]|1[0-2])[/\-](19|20)\d{2}\b"),
    # Month-name YYYY (e.g. "Jan 2024", "March 2023")
    re.compile(
        r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
        r"Dec(?:ember)?)\s*(19|20)\d{2}\b",
        re.IGNORECASE,
    ),
    # YYYY-MM-DD (ISO)
    re.compile(r"\b(19|20)\d{2}[/\-](0[1-9]|1[0-2])[/\-](0[1-9]|[12]\d|3[01])\b"),
]


@register_rule(
    rule_id="6_1_f",
    description=_DESCRIPTION,
    citation=_CITATION,
    category="date",
)
def check_date_of_manufacture(fields: dict) -> RuleResult:
    """Validates that a date of manufacture/packing is present in a recognizable format."""
    date_val = fields.get("date_of_manufacture")

    if date_val is None or str(date_val).strip() == "":
        return RuleResult(
            passed=False,
            rule_id="6_1_f",
            description=_DESCRIPTION,
            citation=_CITATION,
            extracted_value=None,
            reason="Date of manufacture/packing declaration is missing from the label.",
        )

    date_str = str(date_val).strip()

    for pattern in _DATE_PATTERNS:
        if pattern.search(date_str):
            return RuleResult(
                passed=True,
                rule_id="6_1_f",
                description=_DESCRIPTION,
                citation=_CITATION,
                extracted_value=date_str,
            )

    return RuleResult(
        passed=False,
        rule_id="6_1_f",
        description=_DESCRIPTION,
        citation=_CITATION,
        extracted_value=date_str,
        reason=(
            f"Date value '{date_str}' is not in a recognized date format "
            "(expected MM/YYYY, DD/MM/YYYY, Month YYYY, or YYYY-MM-DD)."
        ),
    )
