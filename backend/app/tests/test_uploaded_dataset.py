"""Test suite running the full OCR and Legal Metrology rule engine pipeline
across the user-uploaded real product images in backend/uploads/.
Ensures that at least 20 real product images are tested and successfully process
through the complete pipeline without crashing or unhandled exceptions.
"""

from pathlib import Path
import pytest

from app.services.preprocessing import preprocess_image
from app.services.ocr import extract_text, OCRBlock
from app.services.parser import classify_fields, get_field_confidences
import app.rules
from app.rules.registry import run_all_rules


UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"


def get_uploaded_test_images() -> list[Path]:
    """Retrieve all real uploaded product images from backend/uploads/."""
    if not UPLOADS_DIR.exists():
        return []
    # Real photos uploaded with valid file size (>10KB)
    images = sorted([
        f for f in UPLOADS_DIR.glob("*.jpg")
        if f.is_file() and f.stat().st_size > 10000
    ])
    return images



def test_at_least_20_uploaded_images_available():
    """Verify that at least 20 real product images are present in backend/uploads/."""
    images = get_uploaded_test_images()
    assert len(images) >= 20, f"Expected at least 20 uploaded images, but found {len(images)}"


@pytest.mark.parametrize("image_idx", range(20))
def test_pipeline_runs_successfully_on_uploaded_image(image_idx: int):
    """Test that each of the first 20 uploaded images executes completely through:
    1. OpenCV Preprocessing (downscaling, CLAHE, bilateral filter)
    2. EasyOCR text extraction (returns OCRBlock list without crashing)
    3. Field classification (extracts MRP, Net Qty, Date, Mfg, Consumer Care)
    4. Legal Metrology rule validation (RuleResult for all 5 statutory rules)
    """
    images = get_uploaded_test_images()
    assert len(images) > image_idx, f"Image at index {image_idx} not found"

    image_path = images[image_idx]
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    assert len(image_bytes) > 0, f"Image {image_path.name} is empty"

    # Step 1: Preprocessing
    preprocessed = preprocess_image(image_bytes)
    assert preprocessed is not None
    assert len(preprocessed.shape) == 2  # Grayscale
    assert max(preprocessed.shape) <= 1600  # Downscaled for memory safety

    # Step 2: OCR Text Extraction
    ocr_blocks = extract_text(preprocessed)
    assert isinstance(ocr_blocks, list)
    for block in ocr_blocks:
        assert isinstance(block, OCRBlock)
        assert isinstance(block.text, str)
        assert 0.0 <= block.confidence <= 1.0

    # Step 3: Field Classification
    classified = classify_fields(ocr_blocks)
    assert isinstance(classified, dict)
    expected_keys = {
        "mrp",
        "net_quantity",
        "date_of_manufacture",
        "manufacturer_name",
        "manufacturer_address",
        "consumer_care",
    }
    assert expected_keys.issubset(classified.keys())

    confidences = get_field_confidences(ocr_blocks)
    assert isinstance(confidences, dict)
    assert expected_keys.issubset(confidences.keys())


    # Step 4: Rule Engine Execution
    rule_results = run_all_rules(classified)
    assert isinstance(rule_results, list)
    assert len(rule_results) == 5
    passed_count = sum(1 for r in rule_results if r.passed)
    failed_count = sum(1 for r in rule_results if not r.passed)
    assert passed_count + failed_count == 5
    for r in rule_results:
        assert hasattr(r, "rule_id")
        assert hasattr(r, "passed")
        assert isinstance(r.passed, bool)

