import re

from app.rules.registry import RuleResult, register_rule

_CITATION = (
    "Rule 6(1)(g), Legal Metrology (Packaged Commodities) Rules, 2011 — "
    "Every package shall bear details of the consumer care information, "
    "including contact details such as telephone number, email address, "
    "or other means of communication."
)
_DESCRIPTION = "Consumer care contact details must be declared on the package"

# Phone: Indian landline/mobile patterns, or toll-free 1800 numbers
_PHONE_PATTERN = re.compile(
    r"(?:\+?91[\s\-]?)?[6-9]\d{9}\b"      # 10-digit mobile (optional +91 or 91)
    r"|(?:\+91[\s\-]?)?(?:\d[\s\-]?){10}"  # generic 10-digit
    r"|1800[\s\-]?\d{3}[\s\-]?\d{3,5}\b"  # toll-free
    r"|(?:\+?91[\s\-]?)?(?:0?[1-9]\d{1,4}[\s\-]?)?(?:\d[\s\-]?){7,8}\b",  # landline with STD
)

_EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


@register_rule(
    rule_id="6_1_g",
    description=_DESCRIPTION,
    citation=_CITATION,
    category="consumer_care",
    severity="minor",
)
def check_consumer_care(fields: dict) -> RuleResult:
    """Validates that consumer care info is present and contains a phone number or email."""
    care_val = fields.get("consumer_care")

    if care_val is None or str(care_val).strip() == "":
        return RuleResult(
            passed=False,
            rule_id="6_1_g",
            description=_DESCRIPTION,
            citation=_CITATION,
            extracted_value=None,
            reason="Consumer care contact details are missing from the label.",
        )

    care_str = str(care_val).strip()

    has_phone = bool(_PHONE_PATTERN.search(care_str))
    has_email = bool(_EMAIL_PATTERN.search(care_str))

    if not has_phone and not has_email:
        return RuleResult(
            passed=False,
            rule_id="6_1_g",
            description=_DESCRIPTION,
            citation=_CITATION,
            extracted_value=care_str,
            reason=(
                f"Consumer care value '{care_str}' does not contain a recognizable "
                "phone number or email address."
            ),
        )

    return RuleResult(
        passed=True,
        rule_id="6_1_g",
        description=_DESCRIPTION,
        citation=_CITATION,
        extracted_value=care_str,
    )
