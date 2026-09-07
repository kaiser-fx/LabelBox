"""Tests for the rule registry — run_all_rules, get_rule, and get_all_rules."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import app.rules  # noqa: E402 — triggers registration of all rules
from app.rules.registry import run_all_rules, get_rule, get_all_rules  # noqa: E402


# A complete, valid set of fields representing a compliant product label
VALID_FIELDS = {
    "mrp": "₹150.00",
    "net_quantity": "500 g",
    "manufacturer_name": "Acme Foods Pvt. Ltd.",
    "manufacturer_address": "Plot 42, Industrial Area Phase II, Gurgaon, Haryana 122015",
    "date_of_manufacture": "03/2024",
    "consumer_care": "1800-123-4567",
}

# All fields missing
EMPTY_FIELDS: dict = {}

# Partial: only MRP and net quantity present
PARTIAL_FIELDS = {
    "mrp": "Rs. 85",
    "net_quantity": "200 ml",
}


class TestRunAllRules:
    def test_all_rules_pass_with_valid_fields(self):
        results = run_all_rules(VALID_FIELDS)
        assert len(results) == 5
        for r in results:
            assert r.passed is True, f"Rule {r.rule_id} unexpectedly failed: {r.reason}"

    def test_all_rules_fail_with_empty_fields(self):
        results = run_all_rules(EMPTY_FIELDS)
        assert len(results) == 5
        for r in results:
            assert r.passed is False, f"Rule {r.rule_id} unexpectedly passed"
            assert r.citation, f"Rule {r.rule_id} missing citation"
            assert r.reason, f"Rule {r.rule_id} missing failure reason"

    def test_partial_fields_mixed_results(self):
        results = run_all_rules(PARTIAL_FIELDS)
        assert len(results) == 5

        result_map = {r.rule_id: r for r in results}

        assert result_map["6_1_e"].passed is True, "MRP should pass"
        assert result_map["6_1_a"].passed is True, "Net quantity should pass"
        assert result_map["6_1_b"].passed is False, "Manufacturer should fail"
        assert result_map["6_1_f"].passed is False, "Date should fail"
        assert result_map["6_1_g"].passed is False, "Consumer care should fail"

    def test_results_contain_citations(self):
        results = run_all_rules(EMPTY_FIELDS)
        for r in results:
            assert "Legal Metrology" in r.citation
            assert "Rule 6(1)" in r.citation


class TestGetRule:
    def test_get_existing_rule(self):
        rule = get_rule("6_1_e")
        assert rule is not None
        assert rule.rule_id == "6_1_e"
        assert rule.category == "mrp"

    def test_get_nonexistent_rule(self):
        rule = get_rule("nonexistent_rule")
        assert rule is None


class TestGetAllRules:
    def test_all_five_rules_registered(self):
        all_rules = get_all_rules()
        assert len(all_rules) == 5
        expected_ids = {"6_1_e", "6_1_a", "6_1_b", "6_1_f", "6_1_g"}
        assert set(all_rules.keys()) == expected_ids

    def test_each_rule_has_required_metadata(self):
        for rule_id, rule_def in get_all_rules().items():
            assert rule_def.rule_id == rule_id
            assert rule_def.description
            assert rule_def.citation
            assert rule_def.category
            assert callable(rule_def.validate)
