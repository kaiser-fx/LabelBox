import sys
sys.path.insert(0, ".")
import re
from pathlib import Path
from app.services.preprocessing import preprocess_image
from app.services.ocr import extract_text, OCRBlock

# Test MRP normalization for MRP (<)
mrp_text = "MRP (<) 2999 00 (Inclusive of all taxes)"
normalized = re.sub(r"\bMRP\s*[:\-]?\s*\(?<\)?\s*", "MRP: ₹ ", mrp_text, flags=re.IGNORECASE)
normalized = re.sub(r"(\d+)\s+00\b", r"\1.00", normalized)
print("Normalized MRP:", normalized)

# Test Date normalization for MFG. DATE 06 (2825
date_text = "MFG. DATE: 06 (2825"
normalized_d = re.sub(r"\(\s*2825", "2026", date_text)
normalized_d = re.sub(r"(\b\d{2})\s+(\d{4}\b)", r"\1/\2", normalized_d)
print("Normalized Date:", normalized_d)

# Test Manufacturer trigger on Rajkamal and Protein
MFR_TRIGGER = re.compile(
    r"\b((?:(?:[AMm]anufactured|AnufaciLred|Mfg|Mfd|Packed|Pkd|Marketed|Mkt|Imported)\s*(?:&|\band\b)?\s*(?:Packed|Marketed|Mfg|Pkd)?\s*(?:by|bv|uy|By|Bv|Uy|:)|\bManufactured\b)|Packer\s*:|Importer\s*:)\b",
    re.IGNORECASE,
)
print("MFR matches Rajkamal:", bool(MFR_TRIGGER.search("& Packed Bv:")))
print("MFR matches Protein:", bool(MFR_TRIGGER.search("AnufaciLred Uy:")))
