import cv2
import numpy as np


def preprocess_image(image_bytes: bytes) -> np.ndarray:
    """Preprocess image bytes for OCR:
    - Decode byte stream to OpenCV BGR image
    - Convert to grayscale
    - Normalize contrast using CLAHE (Contrast Limited Adaptive Histogram Equalization)
    - Apply bilateral filter to reduce noise while keeping edge sharpness
    """
    if not image_bytes:
        raise ValueError("Empty image bytes provided")

    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if image is None:
        raise ValueError("Could not decode image bytes. Unsupported or corrupted format.")

    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Adaptive histogram equalization for contrast normalization
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    contrast_normalized = clahe.apply(gray)

    # Bilateral filter removes noise while keeping edges sharp (critical for text OCR)
    denoised = cv2.bilateralFilter(contrast_normalized, d=7, sigmaColor=50, sigmaSpace=50)

    return denoised
