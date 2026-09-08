import sys
sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path

import json

from app.services.preprocessing import preprocess_image
from app.services.ocr import extract_text
from app.services.parser import classify_fields
import app.rules
from app.rules.registry import run_all_rules

test_dir = Path("uploads/test files")
images = sorted([f for f in test_dir.iterdir() if f.is_file() and f.suffix.lower() in [".jpg", ".jpeg", ".png"]])

print(f"Processing {len(images)} images in {test_dir}...\n")

summary = []
for idx, img in enumerate(images, 1):
    with open(img, "rb") as f:
        img_bytes = f.read()
    preprocessed = preprocess_image(img_bytes)
    blocks = extract_text(preprocessed)
    classified = classify_fields(blocks)
    rules = run_all_rules(classified)
    passed_rules = [r.rule_id for r in rules if r.passed]
    failed_rules = [r.rule_id for r in rules if not r.passed]
    
    row = {
        "filename": img.name,
        "blocks": len(blocks),
        "mrp": classified.get("mrp"),
        "net_qty": classified.get("net_quantity"),
        "mfg_date": classified.get("date_of_manufacture"),
        "manufacturer": classified.get("manufacturer_name"),
        "address": classified.get("manufacturer_address"),
        "consumer_care": classified.get("consumer_care"),
        "passed_rules_count": len(passed_rules),
        "failed_rules_count": len(failed_rules),
        "failed_rules": failed_rules,
    }
    summary.append(row)
    print(f"[{idx}/{len(images)}] {img.name}: {len(blocks)} blocks | Rules: {len(passed_rules)} PASS, {len(failed_rules)} FAIL")
    print(f"    MRP: {row['mrp']}")
    print(f"    Net Qty: {row['net_qty']}")
    print(f"    Mfg Date: {row['mfg_date']}")
    print(f"    Manufacturer: {row['manufacturer']}")
    print(f"    Address: {row['address']}")
    print(f"    Consumer Care: {row['consumer_care']}")
    print("-" * 60)

with open("scratch/test_files_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)

print("\nSaved detailed results to scratch/test_files_summary.json")
