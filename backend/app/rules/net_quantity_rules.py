import re

from app.rules.registry import RuleResult, register_rule

# Units recognised under the Legal Metrology Act for packaged commodities (including common OCR readings of ml)
VALID_UNITS = re.compile(
    r"\b(\d+(?:[.,]\d+)?)\s*(g|gm|gms|gram|grams|kg|kilogram|kilograms|"
    r"ml|mi|m1|mil|me|mks|mls|millilitre|millilitres|milliliter|milliliters|"
    r"l|litre|litres|liter|liters|"
    r"cm|mm|pieces|pcs|nos|units|pack|packs|n)\b"
    r"|\bpack\s+of\s*\d+\b",
    re.IGNORECASE,
)




@register_rule(
    rule_id="6_1_a",
    description="Net quantity must be declared on the package",
    citation=(
        "Rule 6(1)(a), Legal Metrology (Packaged Commodities) Rules, 2011 — "
        "Every package shall bear a declaration of the net quantity of the commodity "
        "contained in the package, expressed in terms of standard units of weight or measure."
    ),
    category="net_quantity",
    severity="major",
)
def check_net_quantity_declared(fields: dict) -> RuleResult:
    """Validates that net quantity is present with a numeric value and a recognized unit."""
    net_qty = fields.get("net_quantity")

    if net_qty is None or str(net_qty).strip() == "":
        return RuleResult(
            passed=False,
            rule_id="6_1_a",
            description="Net quantity must be declared on the package",
            citation=(
                "Rule 6(1)(a), Legal Metrology (Packaged Commodities) Rules, 2011 — "
                "Every package shall bear a declaration of the net quantity of the commodity "
                "contained in the package, expressed in terms of standard units of weight or measure."
            ),
            extracted_value=None,
            reason="Net quantity declaration is missing from the label.",
        )

    net_qty_str = str(net_qty).strip()
    match = VALID_UNITS.search(net_qty_str)

    if not match:
        return RuleResult(
            passed=False,
            rule_id="6_1_a",
            description="Net quantity must be declared on the package",
            citation=(
                "Rule 6(1)(a), Legal Metrology (Packaged Commodities) Rules, 2011 — "
                "Every package shall bear a declaration of the net quantity of the commodity "
                "contained in the package, expressed in terms of standard units of weight or measure."
            ),
            extracted_value=net_qty_str,
            reason=(
                f"Net quantity '{net_qty_str}' does not contain a recognized "
                "numeric value with a standard unit of weight or measure."
            ),
        )

    return RuleResult(
        passed=True,
        rule_id="6_1_a",
        description="Net quantity must be declared on the package",
        citation=(
            "Rule 6(1)(a), Legal Metrology (Packaged Commodities) Rules, 2011 — "
            "Every package shall bear a declaration of the net quantity of the commodity "
            "contained in the package, expressed in terms of standard units of weight or measure."
        ),
        extracted_value=net_qty_str,
    )
