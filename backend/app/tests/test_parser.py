"""Tests for the field classification / parser service."""

import pytest
from app.services.ocr import OCRBlock
from app.services.parser import (
    classify_fields,
    get_field_confidences,
    _extract_mrp,
    _extract_net_quantity,
    _extract_date,
    _extract_manufacturer,
    _extract_consumer_care,
)


def _make_block(
    text: str,
    confidence: float = 0.9,
    bounding_box: list[list[int]] | None = None,
) -> OCRBlock:
    """Helper to create an OCRBlock with minimal bounding box."""
    return OCRBlock(
        text=text,
        confidence=confidence,
        bounding_box=bounding_box or [[0, 0], [100, 0], [100, 30], [0, 30]],
    )



# ── MRP Extraction ──────────────────────────────────────────────────────────

class TestMRPExtraction:
    def test_mrp_with_rupee_symbol(self):
        blocks = [_make_block("MRP ₹249.00 (Incl. of all taxes)")]
        result = classify_fields(blocks)
        assert result["mrp"] is not None
        assert "249" in result["mrp"]

    def test_mrp_with_rs_prefix(self):
        blocks = [_make_block("M.R.P Rs. 150.00")]
        result = classify_fields(blocks)
        assert result["mrp"] is not None
        assert "150" in result["mrp"]

    def test_mrp_split_across_blocks(self):
        blocks = [
            _make_block("MRP"),
            _make_block("Rs. 99.50"),
        ]
        result = classify_fields(blocks)
        assert result["mrp"] is not None
        assert "99" in result["mrp"]

    def test_mrp_missing(self):
        blocks = [_make_block("Some random text without price")]
        result = classify_fields(blocks)
        assert result["mrp"] is None

    def test_mrp_maximum_retail_price_keyword(self):
        blocks = [_make_block("Maximum Retail Price: Rs 320")]
        result = classify_fields(blocks)
        assert result["mrp"] is not None
        assert "320" in result["mrp"]

    def test_mrp_with_city_and_price_in_adjacent_block(self):
        blocks = [
            _make_block("MRP 0/5 MUMBAI Rs."),
            _make_block("70 / -"),
        ]
        result = classify_fields(blocks)
        assert result["mrp"] is not None
        assert "70" in result["mrp"]
        assert "MUMBAI" in result["mrp"]

    def test_mrp_with_slash_dash_format(self):
        blocks = [_make_block("MRP Rs. 70/-")]
        result = classify_fields(blocks)
        assert result["mrp"] is not None
        assert "70" in result["mrp"]

    def test_mrp_price_after_date_rows(self):
        blocks = [
            _make_block("MRP Rs"),
            _make_block("01/2024"),
            _make_block("12/2026"),
            _make_block("₹ 120"),
        ]
        result = classify_fields(blocks)
        assert result["mrp"] == "MRP Rs ₹ 120"


# ── Net Quantity Extraction ──────────────────────────────────────────────────

class TestNetQuantityExtraction:
    def test_net_qty_standard(self):
        blocks = [_make_block("Net Qty: 500 g")]
        result = classify_fields(blocks)
        assert result["net_quantity"] is not None
        assert "500" in result["net_quantity"]

    def test_net_weight_kg(self):
        blocks = [_make_block("Net Weight 1.5 kg")]
        result = classify_fields(blocks)
        assert result["net_quantity"] is not None
        assert "1.5" in result["net_quantity"]

    def test_net_qty_ml(self):
        blocks = [_make_block("Net Content: 200 ml")]
        result = classify_fields(blocks)
        assert result["net_quantity"] is not None
        assert "200" in result["net_quantity"]

    def test_net_qty_split_blocks(self):
        blocks = [
            _make_block("Net Qty"),
            _make_block("250 gm"),
        ]
        result = classify_fields(blocks)
        assert result["net_quantity"] is not None
        assert "250" in result["net_quantity"]

    def test_net_qty_missing(self):
        blocks = [_make_block("Just some text")]
        result = classify_fields(blocks)
        assert result["net_quantity"] is None


# ── Date of Manufacture Extraction ───────────────────────────────────────────

class TestDateExtraction:
    def test_mfg_date_mm_yyyy(self):
        blocks = [_make_block("Mfg Date: 08/2026")]
        result = classify_fields(blocks)
        assert result["date_of_manufacture"] is not None
        assert "08/2026" in result["date_of_manufacture"]

    def test_mfg_date_dd_mm_yyyy(self):
        blocks = [_make_block("Mfd: 15/08/2026")]
        result = classify_fields(blocks)
        assert result["date_of_manufacture"] is not None
        assert "15/08/2026" in result["date_of_manufacture"]

    def test_mfg_date_month_name(self):
        blocks = [_make_block("Packed on: Jan 2026")]
        result = classify_fields(blocks)
        assert result["date_of_manufacture"] is not None
        assert "Jan" in result["date_of_manufacture"]

    def test_best_before_trigger(self):
        blocks = [_make_block("Best Before: 03/2027")]
        result = classify_fields(blocks)
        assert result["date_of_manufacture"] is not None
        assert "03/2027" in result["date_of_manufacture"]

    def test_date_split_blocks(self):
        blocks = [
            _make_block("Mfg Dt"),
            _make_block("09/2026"),
        ]
        result = classify_fields(blocks)
        assert result["date_of_manufacture"] is not None
        assert "09/2026" in result["date_of_manufacture"]

    def test_date_missing(self):
        blocks = [_make_block("No date anywhere")]
        result = classify_fields(blocks)
        assert result["date_of_manufacture"] is None


# ── Manufacturer Extraction ──────────────────────────────────────────────────

class TestManufacturerExtraction:
    def test_mfg_by_single_block(self):
        blocks = [_make_block("Mfg by: Sunshine Foods Pvt Ltd, Plot 42, MIDC, Mumbai 400001")]
        result = classify_fields(blocks)
        assert result["manufacturer_name"] is not None
        assert "Sunshine" in result["manufacturer_name"]

    def test_mfg_by_multi_block(self):
        blocks = [
            _make_block("Manufactured by:"),
            _make_block("Tasty Treats India Ltd"),
            _make_block("Industrial Area Phase 2, Chandigarh 160002"),
        ]
        result = classify_fields(blocks)
        assert result["manufacturer_name"] is not None
        assert result["manufacturer_address"] is not None

    def test_marketed_by(self):
        blocks = [_make_block("Marketed by: ABC Corp, New Delhi")]
        result = classify_fields(blocks)
        assert result["manufacturer_name"] is not None

    def test_manufacturer_missing(self):
        blocks = [_make_block("Random text")]
        result = classify_fields(blocks)
        assert result["manufacturer_name"] is None


# ── Consumer Care Extraction ─────────────────────────────────────────────────

class TestConsumerCareExtraction:
    def test_toll_free_number(self):
        blocks = [_make_block("Consumer Helpline: 1800-100-3000")]
        result = classify_fields(blocks)
        assert result["consumer_care"] is not None
        assert "1800" in result["consumer_care"]

    def test_email_address(self):
        blocks = [_make_block("Customer Care: support@sunshine.com")]
        result = classify_fields(blocks)
        assert result["consumer_care"] is not None
        assert "support@sunshine.com" in result["consumer_care"]

    def test_phone_and_email(self):
        blocks = [_make_block("Contact us: 9876543210 or care@brand.in")]
        result = classify_fields(blocks)
        assert result["consumer_care"] is not None

    def test_consumer_care_split_blocks(self):
        blocks = [
            _make_block("Consumer Care"),
            _make_block("1800-200-4000"),
        ]
        result = classify_fields(blocks)
        assert result["consumer_care"] is not None
        assert "1800" in result["consumer_care"]

    def test_consumer_care_missing(self):
        blocks = [_make_block("Nothing relevant")]
        result = classify_fields(blocks)
        assert result["consumer_care"] is None


# ── End-to-End Classification ────────────────────────────────────────────────

class TestEndToEndClassification:
    def test_full_label_classification(self):
        """Simulate a complete product label with all mandatory fields."""
        blocks = [
            _make_block("SUNSHINE CREAM BISCUITS", 0.98),
            _make_block("MRP Rs. 249.00 (Incl. of all taxes)", 0.96),
            _make_block("Net Qty: 500 g", 0.94),
            _make_block("Mfg Date: 08/2026", 0.91),
            _make_block("Best Before 6 Months from Mfg", 0.88),
            _make_block("Mfg by: Sunshine Foods Pvt Ltd", 0.93),
            _make_block("Plot 42, MIDC Industrial Area, Andheri East, Mumbai 400093", 0.90),
            _make_block("Consumer Helpline: 1800-100-3000", 0.95),
            _make_block("care@sunshinefoods.com", 0.92),
        ]
        result = classify_fields(blocks)

        assert result["mrp"] is not None
        assert "249" in result["mrp"]
        assert result["net_quantity"] is not None
        assert "500" in result["net_quantity"]
        assert result["date_of_manufacture"] is not None
        assert "08/2026" in result["date_of_manufacture"]
        assert result["manufacturer_name"] is not None
        assert result["consumer_care"] is not None

    def test_empty_blocks_returns_all_none(self):
        result = classify_fields([])
        assert all(v is None for v in result.values())
        assert len(result) == 6

    def test_classification_feeds_into_rule_engine(self):
        """Verify classified fields dict is compatible with run_all_rules."""
        from app.rules.registry import run_all_rules
        import app.rules  # noqa: F401

        blocks = [
            _make_block("MRP Rs. 249.00 (Incl. of all taxes)", 0.96),
            _make_block("Net Qty: 500 g", 0.94),
            _make_block("Mfg Date: 08/2026", 0.91),
            _make_block("Mfg by: Sunshine Foods Pvt Ltd", 0.93),
            _make_block("Plot 42, MIDC Industrial Area, Andheri East, Mumbai 400093", 0.90),
            _make_block("Consumer Helpline: 1800-100-3000", 0.95),
        ]

        fields = classify_fields(blocks)
        results = run_all_rules(fields)

        # All 5 rules should have run
        assert len(results) == 5

        # All should pass for this complete label
        for r in results:
            assert r.passed, f"Rule {r.rule_id} unexpectedly failed: {r.reason}"

    def test_partial_label_produces_violations(self):
        """A label missing fields should produce failing rule results."""
        from app.rules.registry import run_all_rules
        import app.rules  # noqa: F401

        # Only MRP and net quantity present
        blocks = [
            _make_block("MRP Rs. 100.00"),
            _make_block("Net Qty: 200 g"),
        ]
        fields = classify_fields(blocks)
        results = run_all_rules(fields)

        passed = [r for r in results if r.passed]
        failed = [r for r in results if not r.passed]

        # MRP and net quantity should pass
        assert any(r.rule_id == "6_1_e" and r.passed for r in results)
        assert any(r.rule_id == "6_1_a" and r.passed for r in results)

        # Date, manufacturer, consumer care should fail
        assert any(r.rule_id == "6_1_f" and not r.passed for r in results)
        assert any(r.rule_id == "6_1_b" and not r.passed for r in results)
        assert any(r.rule_id == "6_1_g" and not r.passed for r in results)


class TestFieldConfidences:
    def test_confidences_returned(self):
        blocks = [
            _make_block("MRP Rs. 100.00", 0.95),
            _make_block("Net Qty: 200 g", 0.88),
        ]
        confidences = get_field_confidences(blocks)
        assert confidences["mrp"] is not None
        assert confidences["mrp"] == pytest.approx(0.95, abs=0.01)
        assert confidences["net_quantity"] is not None
        assert confidences["date_of_manufacture"] is None

    def test_empty_blocks_returns_none(self):
        confidences = get_field_confidences([])
        assert all(v is None for v in confidences.values())


class TestOCRArtifactRecovery:
    def test_mrp_with_ocr_rupee_symbol_artifact(self):
        """Test MRP when ₹ was misread by OCR as '{' with tax declaration in following block."""
        blocks = [
            _make_block("MRP", 0.90, [[312, 506], [350, 502], [350, 524], [314, 528]]),
            _make_block("{1749.00 (Incl,", 0.85, [[362, 500], [514, 500], [514, 524], [362, 524]]),
            _make_block("of all Taxes)", 0.90, [[520, 501], [634, 501], [634, 528], [520, 528]]),
        ]
        result = classify_fields(blocks)
        assert result["mrp"] is not None
        assert "1749.00" in result["mrp"]
        assert "Taxes" in result["mrp"]

    def test_net_quantity_with_ocr_mi_typo(self):
        """Test Net Qty when 'ml' was misread by OCR as 'mi' or 'm1'."""
        blocks = [
            _make_block("Net Qty::", 0.85),
            _make_block("200 mi", 0.92),
        ]
        result = classify_fields(blocks)
        assert result["net_quantity"] is not None
        assert "200 ml" in result["net_quantity"]

    def test_spatial_recovery_when_blocks_separated_in_list(self):
        """Test that spatial fallback recovers horizontally aligned MRP and price even if separated in list."""
        blocks = [
            _make_block("{1749.00 (Incl,", 0.85, [[362, 500], [514, 500], [514, 524], [362, 524]]),
            _make_block("Unrelated Text", 0.70, [[10, 100], [200, 100], [200, 130], [10, 130]]),
            _make_block("MRP", 0.90, [[312, 506], [350, 502], [350, 524], [314, 528]]),
        ]
        result = classify_fields(blocks)
        assert result["mrp"] is not None
        assert "1749.00" in result["mrp"]

    def test_ket_quantity_ocr_typo(self):
        """Test Net Quantity when 'Net' was misread by OCR as 'Ket' or 'Met'."""
        blocks = [
            _make_block("Ket Quantity:", 0.88),
            _make_block("118 ml", 0.95),
        ]
        result = classify_fields(blocks)
        assert result["net_quantity"] is not None
        assert "Net" in result["net_quantity"]
        assert "118 ml" in result["net_quantity"]

    def test_mig_date_with_2digit_year(self):
        """Test Date when 'Mfg Date' was misread as 'Mig Date' and date is in MM/YY (10/25)."""
        blocks = [
            _make_block("10/25", 0.99),
            _make_block("Mig Date;", 0.85),
        ]
        result = classify_fields(blocks)
        assert result["date_of_manufacture"] is not None
        assert "10/25" in result["date_of_manufacture"]
        assert "Mfg Date" in result["date_of_manufacture"]

    def test_rajkamal_namkeen_label_fields(self):
        """Test Rajkamal Namkeen label pattern (Manufactured & Packed Bv:, email with space, etc)."""
        blocks = [
            _make_block("DIET NAVRATAN MIX (200 g)"),
            _make_block("Net Wt"),
            _make_block("200 g"),
            _make_block("Pkdt"),
            _make_block("05-09-16"),
            _make_block("MRP IN MUMBAI Rs."),
            _make_block("70 / -"),
            _make_block("Manufactured"),
            _make_block("& Packed Bv:"),
            _make_block("RaJKAMAL NAMKEENSa PVOLLTD"),
            _make_block("24/25, Damji"),
            _make_block("Shamji Ind Est, Vikhroli (WL Mumbai"),
            _make_block("rajkamalnamkeens@gmail com"),
            _make_block("Customer care no ."),
            _make_block("25782103"),
        ]
        result = classify_fields(blocks)
        assert result["mrp"] is not None and "70" in result["mrp"]
        assert result["net_quantity"] is not None and "200 g" in result["net_quantity"]
        assert result["date_of_manufacture"] is not None and "05-09-16" in result["date_of_manufacture"]
        assert result["manufacturer_name"] is not None and "RAJKAMAL NAMKEENS" in result["manufacturer_name"].upper()
        assert result["manufacturer_address"] is not None and "Mumbai" in result["manufacturer_address"]
        assert result["consumer_care"] is not None

    def test_performance_protein_label_fields(self):
        """Test Performance Protein tub pattern (PACK OF 1, split dot-matrix date, (<) MRP)."""
        blocks = [
            _make_block("Email: careobeasuien"),
            _make_block("Mobile"),
            _make_block("91 9599358358"),
            _make_block("AnufaciLred Uy:"),
            _make_block("Fermentis Life Sciences Pvt Ltd"),
            _make_block("Plot no 22, 41, 48, Sector-8 IMT Manesar, Gurugram, Haryana-122051"),
            _make_block("MFG. DATE"),
            _make_block("06"),
            _make_block("EXPIRY"),
            _make_block("11"),
            _make_block("(2825"),
            _make_block("MRP (<)"),
            _make_block("2999"),
            _make_block("00"),
            _make_block("(Inclusive of all taxes)"),
            _make_block("PACK OF"),
        ]
        result = classify_fields(blocks)
        assert result["mrp"] is not None and "2999.00" in result["mrp"]
        assert result["net_quantity"] is not None and "PACK OF 1" in result["net_quantity"]
        assert result["date_of_manufacture"] is not None and "06/2026" in result["date_of_manufacture"]
        assert result["manufacturer_name"] is not None and "Fermentis Life Sciences" in result["manufacturer_name"]
        assert result["manufacturer_address"] is not None and "Gurugram" in result["manufacturer_address"]
        assert result["consumer_care"] is not None and "9599358358" in result["consumer_care"]

    def test_wild_stone_after_shave_label_fields(self):
        """Test realistic OCR blocks from Wild Stone label with revised MRP sticker."""
        blocks = [
            _make_block("WILD STONE"),
            _make_block("AFTER SHAVE LOTION"),
            _make_block("INGREDIENTS : ETHYL ALCOHOL (95 % v/v) ; CONTENT : 85.50"),
            _make_block("MANUFACTURED"),
            _make_block("INDIA BY : READ THE FIRST CHARACTER OF THE"),
            _make_block("MFD: (A) McNAQE CONSUMER PRODUCTS PVT, LTD, PLOT NO,44,45,"),
            _make_block("488,57,.58,59, SECTOR IB,INTEGRATED INDUSTRIAL ESTATE RANIPUR,"),
            _make_block("HARIDWAR - 249 403,UTTARAKHAND, INDIA. MFG: LIc, NO. M"),
            _make_block("MRP"),
            _make_block("NEW"),
            _make_block("riio/-"),
            _make_block("CALL ; +9133 40142100,E-ma"),
            _make_block("Med ;"),
            _make_block("(a59/2025"),
            _make_block("BEST BEFORE"),
            _make_block("08/2028"),
            _make_block("NET CONTENT"),
            _make_block("50 ml"),
        ]
        result = classify_fields(blocks)
        assert result["mrp"] is not None and "110" in result["mrp"]
        assert result["net_quantity"] is not None and "50 ml" in result["net_quantity"]
        assert result["date_of_manufacture"] is not None and "09/2025" in result["date_of_manufacture"]
        assert result["manufacturer_name"] is not None and "McNROE CONSUMER PRODUCTS" in result["manufacturer_name"]
        assert result["manufacturer_address"] is not None and "RANIPUR" in result["manufacturer_address"]
        assert result["consumer_care"] is not None and "40142100" in result["consumer_care"]

    def test_honitus_cough_syrup_label_fields(self):
        """Test realistic OCR blocks from Dabur Honitus label with split Net + Quantity and smudge typo."""
        blocks = [
            _make_block("Honitus Cough Syrup"),
            _make_block("Ayurvedic Medicine"),
            _make_block("Net"),
            _make_block("t Quantity:"),
            _make_block("100 mks"),
            _make_block("Batch;"),
            _make_block("Mfd:"),
            _make_block("Exp,"),
            _make_block("BD1S1O"),
            _make_block("MRP Rs"),
            _make_block("01/2024"),
            _make_block("12/2026"),
            _make_block("4120"),
            _make_block("Mid. by: DabuR INDIA LTD;"),
            _make_block("109, hpsVDc, Industriat Area, Baddi,"),
            _make_block("Visf, Solan (HP 0-473205"),
            _make_block("Regd, Ullice"),
            _make_block("(onsuMer (cll;"),
            _make_block("~mail daburcares@dabur (OM"),
        ]
        result = classify_fields(blocks)
        assert result["net_quantity"] is not None and "100 ml" in result["net_quantity"]
        assert result["manufacturer_name"] is not None and "DabuR INDIA LTD" in result["manufacturer_name"]
        assert result["manufacturer_address"] is not None and "Baddi" in result["manufacturer_address"]
        assert result["consumer_care"] is not None and "daburcares@dabur.com" in result["consumer_care"]

    def test_fuzzy_anchor_matching_for_ocr_typos(self):
        """Verify fuzzy anchor matching catches degraded OCR keywords with character substitutions."""
        blocks = [
            _make_block("Het Quantity: 250 g"),
            _make_block("Makimum Retail Price: ₹ 350"),
            _make_block("Mfa Date: 05/2026"),
            _make_block("Manufacturd by: ABC Healthcare Ltd, Plot 12, Industrial Area, Pune 411001"),
            _make_block("Cansumer Care: 1800 200 3000"),
        ]
        result = classify_fields(blocks)
        assert result["net_quantity"] is not None and "250 g" in result["net_quantity"]
        assert result["mrp"] is not None and "350" in result["mrp"]
        assert result["date_of_manufacture"] is not None and "05/2026" in result["date_of_manufacture"]
        assert result["manufacturer_name"] is not None and "ABC Healthcare Ltd" in result["manufacturer_name"]
        assert result["consumer_care"] is not None and "1800 200 3000" in result["consumer_care"]






