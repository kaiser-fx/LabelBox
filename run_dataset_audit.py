"""Comprehensive audit script to execute the OCR, field extraction, and rule engine pipeline
across all uploaded images in backend/uploads/. Outputs a detailed Markdown report.
"""

import sys
import time
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(backend_dir))

import app.rules
from app.services.preprocessing import preprocess_image
from app.services.ocr import extract_text
from app.services.parser import classify_fields, get_field_confidences
from app.rules.registry import run_all_rules


def audit_images():
    uploads_dir = backend_dir / "uploads"
    images = sorted([
        f for f in uploads_dir.glob("20260907_*.jpg")
        if f.is_file() and f.stat().st_size > 10000
    ])

    print(f"=== Auditing {len(images)} Uploaded Product Images ===")
    results = []

    for i, img_path in enumerate(images, 1):
        t0 = time.time()
        with open(img_path, "rb") as f:
            raw_bytes = f.read()

        size_kb = len(raw_bytes) / 1024
        try:
            preprocessed = preprocess_image(raw_bytes)
            h, w = preprocessed.shape
            ocr_blocks = extract_text(preprocessed)
            classified = classify_fields(ocr_blocks)
            confidences = get_field_confidences(ocr_blocks)
            rule_results = run_all_rules(classified)
            elapsed = time.time() - t0

            passed = sum(1 for r in rule_results if r.passed)
            failed = sum(1 for r in rule_results if not r.passed)
            violations = [
                f"{r.rule_id} ({r.reason[:30]}...)" for r in rule_results if not r.passed
            ]


            results.append({
                "idx": i,
                "filename": img_path.name,
                "size_kb": f"{size_kb:.0f}",
                "dimensions": f"{w}x{h}",
                "ocr_count": len(ocr_blocks),
                "elapsed": f"{elapsed:.1f}s",
                "mrp": classified.get("mrp") or "—",
                "net_qty": classified.get("net_quantity") or "—",
                "mfg_date": classified.get("date_of_manufacture") or "—",
                "manufacturer": (classified.get("manufacturer_name") or "—")[:30],
                "address": (classified.get("manufacturer_address") or "—")[:30],
                "consumer_care": classified.get("consumer_care") or "—",
                "compliance": f"{passed}/{len(rule_results)} passed",

                "status": "PASS" if failed == 0 else "FLAGGED",
            })

            print(f"[{i}/{len(images)}] {img_path.name}: {len(ocr_blocks)} OCR blocks, {passed}/{len(rule_results)} rules passed in {elapsed:.1f}s")

            for k, v in classified.items():
                if v:
                    print(f"    {k}: {v[:60]}")
        except Exception as e:
            elapsed = time.time() - t0
            print(f"[{i}/{len(images)}] {img_path.name}: ERROR ({e}) in {elapsed:.1f}s")
            results.append({
                "idx": i,
                "filename": img_path.name,
                "size_kb": f"{size_kb:.0f}",
                "dimensions": "ERR",
                "ocr_count": 0,
                "elapsed": f"{elapsed:.1f}s",
                "mrp": "ERR",
                "net_qty": "ERR",
                "mfg_date": "ERR",
                "manufacturer": "ERR",
                "consumer_care": "ERR",
                "compliance": "ERROR",
                "status": "ERROR",
            })

    print("\n=== Audit Completed ===")
    return results


if __name__ == "__main__":
    audit_images()
