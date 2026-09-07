import io
import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import HTTPException

from app.api.scans import parse_captured_at
from app.services.preprocessing import preprocess_image
from app.services.ocr import OCRBlock, extract_text


@pytest.fixture
def dummy_jpeg():
    # A minimal valid 1x1 pixel JPEG
    return (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00"
        b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
        b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
        b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342"
        b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4"
        b"\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b"
        b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
    )


# --- Preprocessing Unit Tests ---

def test_preprocess_empty_bytes_raises_error():
    with pytest.raises(ValueError, match="Empty image bytes"):
        preprocess_image(b"")


def test_preprocess_corrupted_bytes_raises_error():
    with pytest.raises(ValueError, match="Could not decode image bytes"):
        preprocess_image(b"not_an_image_binary_data")


def test_preprocess_valid_image(dummy_jpeg):
    result = preprocess_image(dummy_jpeg)
    assert result is not None
    # Output should be 2D numpy array (grayscale)
    assert len(result.shape) == 2


def test_preprocess_real_label_image():
    from pathlib import Path
    image_path = Path(__file__).parent / "test_images" / "biscuit_pack_label.jpg"
    if image_path.exists():
        with open(image_path, "rb") as f:
            bytes_data = f.read()
        processed = preprocess_image(bytes_data)
        assert processed is not None
        assert len(processed.shape) == 2
        # Dimensions must match original 450x700
        assert processed.shape == (450, 700)


def test_parse_captured_at_normalizes_offline_timestamp_to_utc():
    captured_at = parse_captured_at("2026-09-08T10:30:00+05:30")
    assert captured_at.isoformat() == "2026-09-08T05:00:00+00:00"


def test_parse_captured_at_rejects_timestamp_without_timezone():
    with pytest.raises(HTTPException, match="include a timezone"):
        parse_captured_at("2026-09-08T10:30:00")


# --- OCR Unit Tests ---

def test_ocr_extract_text_empty_on_invalid():
    # Never crash on invalid or non-image
    result = extract_text(None)
    assert result == []


def test_ocr_block_dataclass():
    block = OCRBlock(
        text="MRP Rs. 150.00",
        confidence=0.95,
        bounding_box=[[10, 20], [100, 20], [100, 50], [10, 50]],
    )
    assert block.text == "MRP Rs. 150.00"
    assert block.confidence == 0.95
    parsed_bbox = json.loads(block.bounding_box_json())
    assert parsed_bbox == [[10, 20], [100, 20], [100, 50], [10, 50]]


# --- Scan API Endpoints Tests ---

def test_submit_scan_unauthenticated(client, dummy_jpeg):
    files = {"file": ("label.jpg", io.BytesIO(dummy_jpeg), "image/jpeg")}
    response = client.post("/sessions/some-session/scans", files=files)
    assert response.status_code == 401


def test_submit_scan_nonexistent_session(client, auth_headers, dummy_jpeg):
    files = {"file": ("label.jpg", io.BytesIO(dummy_jpeg), "image/jpeg")}
    response = client.post(
        "/sessions/nonexistent-session-id/scans",
        headers=auth_headers,
        files=files,
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@patch("app.api.scans.extract_text")
@patch("app.api.scans.preprocess_image")
def test_submit_scan_success(mock_preprocess, mock_extract, client, auth_headers, dummy_jpeg):
    mock_preprocess.return_value = MagicMock()
    mock_extract.return_value = [
        OCRBlock(
            text="MRP Rs. 249.00 (Incl. of all taxes)",
            confidence=0.96,
            bounding_box=[[50, 100], [200, 100], [200, 130], [50, 130]],
        ),
        OCRBlock(
            text="Net Qty: 500 g",
            confidence=0.92,
            bounding_box=[[50, 140], [180, 140], [180, 170], [50, 170]],
        ),
        OCRBlock(
            text="Mfg Date: 08/2026",
            confidence=0.90,
            bounding_box=[[50, 180], [180, 180], [180, 210], [50, 210]],
        ),
        OCRBlock(
            text="Mfg by: Sunshine Foods Pvt Ltd",
            confidence=0.93,
            bounding_box=[[50, 220], [250, 220], [250, 250], [50, 250]],
        ),
        OCRBlock(
            text="Plot 42, MIDC Industrial Area, Andheri East, Mumbai 400093",
            confidence=0.89,
            bounding_box=[[50, 260], [350, 260], [350, 290], [50, 290]],
        ),
        OCRBlock(
            text="Consumer Helpline: 1800-100-3000",
            confidence=0.95,
            bounding_box=[[50, 300], [250, 300], [250, 330], [50, 330]],
        ),
    ]

    # Create a real session first
    session_res = client.post(
        "/sessions",
        headers=auth_headers,
        json={"store_name": "Test Mart Phase 4", "location": "Connaught Place"},
    )
    assert session_res.status_code == 201
    session_id = session_res.json()["id"]

    # Submit scan
    files = {"file": ("label.jpg", io.BytesIO(dummy_jpeg), "image/jpeg")}
    scan_res = client.post(
        f"/sessions/{session_id}/scans",
        headers=auth_headers,
        files=files,
    )
    assert scan_res.status_code == 201
    scan_data = scan_res.json()

    assert scan_data["id"] is not None
    assert scan_data["session_id"] == session_id
    assert scan_data["status"] == "completed"
    assert len(scan_data["ocr_blocks"]) == 6
    assert scan_data["ocr_blocks"][0]["text"] == "MRP Rs. 249.00 (Incl. of all taxes)"

    # Phase 4: Verify classified fields
    assert "classified_fields" in scan_data
    cf = scan_data["classified_fields"]
    assert cf.get("mrp") is not None
    assert "249" in cf["mrp"]
    assert cf.get("net_quantity") is not None
    assert "500" in cf["net_quantity"]

    # Phase 4: Verify compliance report
    assert "compliance_report" in scan_data
    report = scan_data["compliance_report"]
    assert report is not None
    assert report["total_rules"] == 5
    assert report["passed"] + report["failed"] == 5

    # Phase 4: Verify violations list exists
    assert "violations" in scan_data
    assert isinstance(scan_data["violations"], list)

    # Test GET /scans/{scan_id}
    get_res = client.get(f"/scans/{scan_data['id']}", headers=auth_headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == scan_data["id"]
    assert len(get_res.json()["ocr_blocks"]) == 6
    assert "classified_fields" in get_res.json()
    assert "violations" in get_res.json()

    # Test GET /sessions/{session_id}/scans
    list_res = client.get(f"/sessions/{session_id}/scans", headers=auth_headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1
