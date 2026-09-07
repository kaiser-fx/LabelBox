"""Tests for individual rule validation functions.

Each rule is tested with:
- Valid input → expect pass
- Missing field → expect fail with correct rule_id and citation
- Malformed input → expect fail with descriptive reason
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import app.rules  # noqa: E402 — triggers registration of all rules
from app.rules.mrp_rules import check_mrp_declared  # noqa: E402
from app.rules.net_quantity_rules import check_net_quantity_declared  # noqa: E402
from app.rules.manufacturer_rules import check_manufacturer_declared  # noqa: E402
from app.rules.date_rules import check_date_of_manufacture  # noqa: E402
from app.rules.consumer_care_rules import check_consumer_care  # noqa: E402


# ── MRP Rule 6(1)(e) ──────────────────────────────────────────────────

class TestMRPRule:
    def test_valid_mrp_with_rupee_symbol(self):
        result = check_mrp_declared({"mrp": "₹150.00"})
        assert result.passed is True
        assert result.rule_id == "6_1_e"

    def test_valid_mrp_with_rs_prefix(self):
        result = check_mrp_declared({"mrp": "Rs. 250"})
        assert result.passed is True

    def test_valid_mrp_plain_number(self):
        result = check_mrp_declared({"mrp": "99.50"})
        assert result.passed is True

    def test_valid_mrp_with_mrp_prefix(self):
        result = check_mrp_declared({"mrp": "MRP 350"})
        assert result.passed is True

    def test_missing_mrp(self):
        result = check_mrp_declared({})
        assert result.passed is False
        assert result.rule_id == "6_1_e"
        assert "6(1)(e)" in result.citation
        assert result.reason is not None

    def test_empty_mrp(self):
        result = check_mrp_declared({"mrp": ""})
        assert result.passed is False

    def test_malformed_mrp(self):
        result = check_mrp_declared({"mrp": "price not listed"})
        assert result.passed is False
        assert "not a recognizable price format" in result.reason


# ── Net Quantity Rule 6(1)(a) ─────────────────────────────────────────

class TestNetQuantityRule:
    def test_valid_grams(self):
        result = check_net_quantity_declared({"net_quantity": "500 g"})
        assert result.passed is True
        assert result.rule_id == "6_1_a"

    def test_valid_kg(self):
        result = check_net_quantity_declared({"net_quantity": "1.5 kg"})
        assert result.passed is True

    def test_valid_ml(self):
        result = check_net_quantity_declared({"net_quantity": "200 ml"})
        assert result.passed is True

    def test_valid_litres(self):
        result = check_net_quantity_declared({"net_quantity": "2 litres"})
        assert result.passed is True

    def test_valid_pieces(self):
        result = check_net_quantity_declared({"net_quantity": "10 pieces"})
        assert result.passed is True

    def test_missing_net_quantity(self):
        result = check_net_quantity_declared({})
        assert result.passed is False
        assert result.rule_id == "6_1_a"
        assert "6(1)(a)" in result.citation

    def test_empty_net_quantity(self):
        result = check_net_quantity_declared({"net_quantity": ""})
        assert result.passed is False

    def test_no_unit(self):
        result = check_net_quantity_declared({"net_quantity": "some quantity"})
        assert result.passed is False
        assert "standard unit" in result.reason


# ── Manufacturer Rule 6(1)(b) ────────────────────────────────────────

class TestManufacturerRule:
    def test_valid_manufacturer(self):
        result = check_manufacturer_declared({
            "manufacturer_name": "Acme Foods Pvt. Ltd.",
            "manufacturer_address": "123 Industrial Area, Phase 2, New Delhi 110020",
        })
        assert result.passed is True
        assert result.rule_id == "6_1_b"

    def test_missing_name(self):
        result = check_manufacturer_declared({
            "manufacturer_address": "123 Industrial Area, Phase 2, New Delhi 110020",
        })
        assert result.passed is False
        assert "manufacturer name" in result.reason

    def test_missing_address(self):
        result = check_manufacturer_declared({
            "manufacturer_name": "Acme Foods Pvt. Ltd.",
        })
        assert result.passed is False
        assert "manufacturer address" in result.reason

    def test_both_missing(self):
        result = check_manufacturer_declared({})
        assert result.passed is False
        assert "6(1)(b)" in result.citation

    def test_too_short_address(self):
        result = check_manufacturer_declared({
            "manufacturer_name": "Acme",
            "manufacturer_address": "Delhi",
        })
        assert result.passed is False
        assert "incomplete" in result.reason


# ── Date of Manufacture Rule 6(1)(f) ─────────────────────────────────

class TestDateRule:
    def test_valid_mm_yyyy(self):
        result = check_date_of_manufacture({"date_of_manufacture": "03/2024"})
        assert result.passed is True
        assert result.rule_id == "6_1_f"

    def test_valid_dd_mm_yyyy(self):
        result = check_date_of_manufacture({"date_of_manufacture": "15/03/2024"})
        assert result.passed is True

    def test_valid_month_name_yyyy(self):
        result = check_date_of_manufacture({"date_of_manufacture": "March 2024"})
        assert result.passed is True

    def test_valid_iso_format(self):
        result = check_date_of_manufacture({"date_of_manufacture": "2024-03-15"})
        assert result.passed is True

    def test_valid_abbreviated_month(self):
        result = check_date_of_manufacture({"date_of_manufacture": "Jan 2025"})
        assert result.passed is True

    def test_missing_date(self):
        result = check_date_of_manufacture({})
        assert result.passed is False
        assert "6(1)(f)" in result.citation

    def test_empty_date(self):
        result = check_date_of_manufacture({"date_of_manufacture": ""})
        assert result.passed is False

    def test_malformed_date(self):
        result = check_date_of_manufacture({"date_of_manufacture": "last year"})
        assert result.passed is False
        assert "not in a recognized date format" in result.reason


# ── Consumer Care Rule 6(1)(g) ───────────────────────────────────────

class TestConsumerCareRule:
    def test_valid_phone(self):
        result = check_consumer_care({"consumer_care": "1800-123-4567"})
        assert result.passed is True
        assert result.rule_id == "6_1_g"

    def test_valid_mobile(self):
        result = check_consumer_care({"consumer_care": "+91 9876543210"})
        assert result.passed is True

    def test_valid_email(self):
        result = check_consumer_care({"consumer_care": "care@acmefoods.com"})
        assert result.passed is True

    def test_valid_both(self):
        result = check_consumer_care({
            "consumer_care": "Call 1800-123-4567 or email care@acme.com"
        })
        assert result.passed is True

    def test_missing_consumer_care(self):
        result = check_consumer_care({})
        assert result.passed is False
        assert "6(1)(g)" in result.citation

    def test_empty_consumer_care(self):
        result = check_consumer_care({"consumer_care": ""})
        assert result.passed is False

    def test_no_contact_info(self):
        result = check_consumer_care({"consumer_care": "Contact us for details"})
        assert result.passed is False
        assert "phone number or email" in result.reason
