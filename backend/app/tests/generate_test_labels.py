import os
from pathlib import Path
import cv2
import numpy as np

OUTPUT_DIR = Path(__file__).parent / "test_images"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def create_biscuit_label():
    """Create a realistic food product label photo."""
    # 600x400 background simulating a packaging label
    img = np.full((450, 700, 3), (245, 245, 240), dtype=np.uint8)

    # Draw border frame
    cv2.rectangle(img, (15, 15), (685, 435), (40, 40, 180), 3)
    cv2.rectangle(img, (20, 20), (680, 430), (200, 200, 200), 1)

    # Header / Brand
    cv2.putText(img, "SUNSHINE GLUCOSE BISCUITS", (40, 65), cv2.FONT_HERSHEY_DUPLEX, 1.0, (20, 20, 140), 2)
    cv2.line(img, (40, 85), (660, 85), (40, 40, 180), 2)

    # Declarations
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(img, "Net Quantity: 200 g", (50, 130), font, 0.8, (10, 10, 10), 2)
    cv2.putText(img, "MRP Rs. 35.00 (Incl. of all taxes)", (50, 180), font, 0.8, (10, 10, 10), 2)
    cv2.putText(img, "Unit Sale Price: Rs. 0.175 / g", (50, 225), font, 0.65, (50, 50, 50), 2)
    cv2.putText(img, "Date of Mfg: 05/2026", (50, 270), font, 0.75, (10, 10, 10), 2)
    cv2.putText(img, "Mfd By: PureBakes India Pvt Ltd, Plot 14 Industrial Area, Solan HP", (50, 315), font, 0.55, (20, 20, 20), 1)
    cv2.putText(img, "Consumer Care: care@purebakes.com | Tel: 1800-111-222", (50, 360), font, 0.60, (20, 20, 20), 2)

    # Add slight camera noise & mild angle tilt
    noise = np.random.normal(0, 4, img.shape).astype(np.int16)
    noisy_img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    path = OUTPUT_DIR / "biscuit_pack_label.jpg"
    cv2.imwrite(str(path), noisy_img)
    print(f"Generated {path}")


def create_hair_oil_label():
    """Create a personal care product label photo."""
    img = np.full((400, 650, 3), (250, 252, 250), dtype=np.uint8)

    # Border
    cv2.rectangle(img, (15, 15), (635, 385), (34, 139, 34), 3)

    # Title
    cv2.putText(img, "HERBAL AYURVEDIC HAIR OIL", (45, 60), cv2.FONT_HERSHEY_DUPLEX, 0.9, (20, 100, 20), 2)
    cv2.line(img, (45, 80), (600, 80), (34, 139, 34), 2)

    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(img, "Net Volume: 100 ml", (50, 130), font, 0.8, (15, 15, 15), 2)
    cv2.putText(img, "MRP Rs. 140.00", (50, 180), font, 0.85, (15, 15, 15), 2)
    cv2.putText(img, "Inclusive of all taxes", (320, 180), font, 0.6, (60, 60, 60), 1)
    cv2.putText(img, "Mfg Date: 01/2026", (50, 230), font, 0.75, (15, 15, 15), 2)
    cv2.putText(img, "Manufactured by: Herbal Glow Labs, MIDC Andheri East, Mumbai 400093", (50, 280), font, 0.52, (20, 20, 20), 1)
    cv2.putText(img, "Customer Care: 022-28345678 | support@herbalglow.in", (50, 330), font, 0.60, (20, 20, 20), 2)

    path = OUTPUT_DIR / "hair_oil_label.jpg"
    cv2.imwrite(str(path), img)
    print(f"Generated {path}")


if __name__ == "__main__":
    create_biscuit_label()
    create_hair_oil_label()
