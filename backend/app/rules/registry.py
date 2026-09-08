from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class RuleResult:
    """Outcome of a single rule check against extracted fields."""
    passed: bool
    rule_id: str
    description: str
    citation: str
    extracted_value: str | None = None
    reason: str | None = None


@dataclass
class RuleDefinition:
    """Metadata + callable for one registered rule."""
    rule_id: str
    description: str
    citation: str
    category: str
    severity: str
    validate: Callable[[dict], RuleResult]


_registry: dict[str, RuleDefinition] = {}


def register_rule(
    rule_id: str,
    description: str,
    citation: str,
    category: str,
    severity: str,
) -> Callable:
    """Decorator that registers a validation function in the rule registry.

    Usage:
        @register_rule(
            rule_id="6_1_e",
            description="MRP must be declared",
            citation="Rule 6(1)(e), Legal Metrology ...",
            category="mrp",
        )
        def check_mrp(fields: dict) -> RuleResult:
            ...
    """
    def decorator(fn: Callable[[dict], RuleResult]) -> Callable[[dict], RuleResult]:
        _registry[rule_id] = RuleDefinition(
            rule_id=rule_id,
            description=description,
            citation=citation,
            category=category,
            severity=severity,
            validate=fn,
        )
        return fn
    return decorator


def get_rule(rule_id: str) -> RuleDefinition | None:
    """Look up a single rule by ID."""
    return _registry.get(rule_id)


def get_all_rules() -> dict[str, RuleDefinition]:
    """Return a copy of the full registry."""
    return dict(_registry)


def run_all_rules(fields: dict) -> list[RuleResult]:
    """Run every registered rule against the given extracted-field dict.

    Returns a list of RuleResult, one per rule, in registration order.
    """
    results: list[RuleResult] = []
    for rule_def in _registry.values():
        result = rule_def.validate(fields)
        results.append(result)
    return results
