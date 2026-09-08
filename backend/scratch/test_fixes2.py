import sys
sys.path.insert(0, ".")
import re
from pathlib import Path
from app.services.preprocessing import preprocess_image
from app.services.ocr import extract_text, OCRBlock

CARE_TRIGGER = re.compile(
    r"\b(Consumer|Customer|Helpline|Toll\s*Free|Contact\s*Us|Customer\s*Service|Grievance|Complaint|Feedback|Care)\b",
    re.IGNORECASE,
)

PHONE_PATTERN = re.compile(
    r"(?:\+?91[\s\-]?)?(?:\d[\s\-]?){10}"
    r"|1800[\s\-]?\d{3}[\s\-]?\d{3,5}"
    r"|(?:\+?91[\s\-]?)?(?:0?\d{2,4}[\s\-]?)?\d{6,8}",
)

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\s*\.?\s*(?:com|in|org|net|co\.in|gov\.in|[a-zA-Z]{2,})", re.IGNORECASE)

img1 = r"C:\Users\ksgrt\.gemini\antigravity-ide\brain\d8f79961-7c32-451f-8088-44d4c06db7ef\.user_uploaded\media_1788821585549.jpg"
img2 = r"C:\Users\ksgrt\.gemini\antigravity-ide\brain\d8f79961-7c32-451f-8088-44d4c06db7ef\.user_uploaded\media_1788821589867.jpg"

with open(img1, "rb") as f: b1 = extract_text(preprocess_image(f.read()))
with open(img2, "rb") as f: b2 = extract_text(preprocess_image(f.read()))

def test_care(blocks, label):
    print(f"\n--- Testing Care on {label} ---")
    # Check if direct email or phone anywhere
    for b in blocks:
        if EMAIL_PATTERN.search(b.text):
            print(f"Direct email in block: '{b.text}'")
    for i, b in enumerate(blocks):
        if CARE_TRIGGER.search(b.text):
            print(f"Trigger in [{i}]: '{b.text}'")
            for j in range(i, min(i + 8, len(blocks))):
                text = blocks[j].text
                if PHONE_PATTERN.search(text) or EMAIL_PATTERN.search(text):
                    print(f"  Found contact in [{j}]: '{text}'")

test_care(b1, "Rajkamal")
test_care(b2, "Protein")
