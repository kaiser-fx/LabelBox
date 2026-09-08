"""Test suite running the full OCR and Legal Metrology rule engine pipeline
across all images in backend/uploads/test files/.
Ensures that every test image in the folder successfully processes through the
complete pipeline without crashing, and verifies extracted fields and statutory compliance.
"""

from pathlib import Path
import pytest

from app.services.preprocessing import preprocess_image
from app.services.ocr import extract_text, OCRBlock
from app.services.parser import classify_fields, get_field_confidences
import app.rules
from app.rules.registry import run_all_rules


TEST_FILES_DIR = Path(__file__).resolve().parent.parent.parent / "uploads" / "test files"


def get_test_files_images() -> list[Path]:
    """Retrieve all image files in backend/uploads/test files/."""
    if not TEST_FILES_DIR.exists():
        return []
    images = sorted([
        f for f in TEST_FILES_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in [".jpg", ".jpeg", ".png"] and f.stat().st_size > 1000
    ])
    return images


def test_test_files_images_exist():
    """Verify that images exist in backend/uploads/test files/."""
    images = get_test_files_images()
    assert len(images) > 0, f"No images found in {TEST_FILES_DIR}"


@pytest.mark.parametrize("image_path", get_test_files_images(), ids=lambda p: p.name)
def test_pipeline_on_each_test_file_image(image_path: Path):
    """Test full pipeline execution on each individual image in test files/."""
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    assert len(image_bytes) > 0, f"Image {image_path.name} is empty"

    # Step 1: Preprocessing
    preprocessed = preprocess_image(image_bytes)
    assert preprocessed is not None
    assert len(preprocessed.shape) == 2  # Grayscale
    assert max(preprocessed.shape) <= 1600

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
    for r in rule_results:
        assert hasattr(r, "rule_id")
        assert hasattr(r, "passed")
        assert isinstance(r.passed, bool)
