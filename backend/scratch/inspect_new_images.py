import sys
sys.path.insert(0, ".")
import re
from pathlib import Path
from app.services.preprocessing import preprocess_image
from app.services.ocr import extract_text, OCRBlock

img1 = r"C:\Users\ksgrt\.gemini\antigravity-ide\brain\d8f79961-7c32-451f-8088-44d4c06db7ef\.user_uploaded\media_1788821585549.jpg"
img2 = r"C:\Users\ksgrt\.gemini\antigravity-ide\brain\d8f79961-7c32-451f-8088-44d4c06db7ef\.user_uploaded\media_1788821589867.jpg"

with open(img1, "rb") as f:
    blocks1 = extract_text(preprocess_image(f.read()))
with open(img2, "rb") as f:
    blocks2 = extract_text(preprocess_image(f.read()))

print("=== IMAGE 1 (RAJKAMAL) BLOCKS 50 to 76 ===")
for i in range(50, len(blocks1)):
    print(f"[{i}] ({blocks1[i].confidence:.2f}) {blocks1[i].text}")

print("\n=== IMAGE 2 (PROTEIN) BLOCKS 12 to 45 ===")
for i in range(12, 43):
    print(f"[{i}] ({blocks2[i].confidence:.2f}) {blocks2[i].text}")
