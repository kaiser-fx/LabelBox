import re

from app.rules.registry import RuleResult, register_rule


@register_rule(
    rule_id="6_1_e",
    description="Maximum Retail Price (MRP) must be declared on the package",
    citation=(
        "Rule 6(1)(e), Legal Metrology (Packaged Commodities) Rules, 2011 — "
        "Every package shall bear the retail sale price of the package."
    ),
    category="mrp",
    severity="major",
)
def check_mrp_declared(fields: dict) -> RuleResult:
    """Validates that the MRP field is present and contains a plausible price value.

    Accepts formats like '₹100', 'Rs. 100.00', 'MRP 250', '99.50', etc.
    """
    mrp = fields.get("mrp")

    if mrp is None or str(mrp).strip() == "":
        return RuleResult(
            passed=False,
            rule_id="6_1_e",
            description="Maximum Retail Price (MRP) must be declared on the package",
            citation=(
                "Rule 6(1)(e), Legal Metrology (Packaged Commodities) Rules, 2011 — "
                "Every package shall bear the retail sale price of the package."
            ),
            extracted_value=None,
            reason="MRP declaration is missing from the label.",
        )

    mrp_str = str(mrp).strip()
    # Match a numeric price, optionally preceded by currency symbols/text
    price_pattern = re.compile(
        r"(?:₹|Rs\.?|MRP\.?|INR)?\s*(\d+(?:[.,]\d{1,2})?)", re.IGNORECASE
    )
    match = price_pattern.search(mrp_str)

    if not match:
        return RuleResult(
            passed=False,
            rule_id="6_1_e",
            description="Maximum Retail Price (MRP) must be declared on the package",
            citation=(
                "Rule 6(1)(e), Legal Metrology (Packaged Commodities) Rules, 2011 — "
                "Every package shall bear the retail sale price of the package."
            ),
            extracted_value=mrp_str,
            reason=f"MRP value '{mrp_str}' is not a recognizable price format.",
        )

    return RuleResult(
        passed=True,
        rule_id="6_1_e",
        description="Maximum Retail Price (MRP) must be declared on the package",
        citation=(
            "Rule 6(1)(e), Legal Metrology (Packaged Commodities) Rules, 2011 — "
            "Every package shall bear the retail sale price of the package."
        ),
        extracted_value=mrp_str,
    )
