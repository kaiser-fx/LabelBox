import sys
sys.path.insert(0, ".")
from pathlib import Path
from app.services.preprocessing import preprocess_image
from app.services.ocr import extract_text
from app.services.parser import classify_fields
import app.rules
from app.rules.registry import run_all_rules

p = Path("uploads/test files/73808610-1fa5-47e2-b2bd-9c7999da6fb4.jpg")
with open(p, "rb") as f:
    blocks = extract_text(preprocess_image(f.read()))

classified = classify_fields(blocks)
print("=== CLASSIFIED FIELDS ===")
for k, v in classified.items():
    print(f"{k}: {v}")

print("\n=== COMPLIANCE EVALUATION ===")
results = run_all_rules(classified)
for r in results:
    status = "PASS" if r.passed else "FAIL"
    print(f"[{status}] Rule {r.rule_id} ({r.description}): extracted={r.extracted_value}")
