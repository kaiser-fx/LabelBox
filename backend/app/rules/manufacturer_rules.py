from app.rules.registry import RuleResult, register_rule

_CITATION = (
    "Rule 6(1)(b), Legal Metrology (Packaged Commodities) Rules, 2011 — "
    "Every package shall bear the name and complete address of the "
    "manufacturer or packer or importer."
)
_DESCRIPTION = (
    "Manufacturer/packer name and address must be declared on the package"
)


@register_rule(
    rule_id="6_1_b",
    description=_DESCRIPTION,
    citation=_CITATION,
    category="manufacturer",
    severity="critical",
)
def check_manufacturer_declared(fields: dict) -> RuleResult:
    """Validates that manufacturer name and address are both present and non-trivially filled.

    A minimal address heuristic: at least 10 characters (short strings like 'India' alone
    aren't a complete address).
    """
    mfr_name = fields.get("manufacturer_name")
    mfr_addr = fields.get("manufacturer_address")

    missing_parts: list[str] = []

    if mfr_name is None or str(mfr_name).strip() == "":
        missing_parts.append("manufacturer name")

    if mfr_addr is None or str(mfr_addr).strip() == "":
        missing_parts.append("manufacturer address")

    if missing_parts:
        return RuleResult(
            passed=False,
            rule_id="6_1_b",
            description=_DESCRIPTION,
            citation=_CITATION,
            extracted_value=None,
            reason=f"Missing: {', '.join(missing_parts)}.",
        )

    mfr_addr_str = str(mfr_addr).strip()
    # A complete address should be reasonably long
    if len(mfr_addr_str) < 10:
        return RuleResult(
            passed=False,
            rule_id="6_1_b",
            description=_DESCRIPTION,
            citation=_CITATION,
            extracted_value=mfr_addr_str,
            reason=(
                f"Manufacturer address '{mfr_addr_str}' appears incomplete "
                "(less than 10 characters)."
            ),
        )

    combined = f"{str(mfr_name).strip()} — {mfr_addr_str}"
    return RuleResult(
        passed=True,
        rule_id="6_1_b",
        description=_DESCRIPTION,
        citation=_CITATION,
        extracted_value=combined,
    )
