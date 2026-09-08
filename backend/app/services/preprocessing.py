import cv2
import numpy as np

MAX_OCR_DIMENSION = 1600


def _downscale_for_ocr(image: np.ndarray) -> np.ndarray:
    """Bound OCR memory use while retaining label text at a readable resolution."""
    height, width = image.shape[:2]
    largest_dimension = max(height, width)
    if largest_dimension <= MAX_OCR_DIMENSION:
        return image

    scale = MAX_OCR_DIMENSION / largest_dimension
    return cv2.resize(
        image,
        (round(width * scale), round(height * scale)),
        interpolation=cv2.INTER_AREA,
    )


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

    # EasyOCR's detector expands intermediate tensors sharply on full 12 MP photos.
    # A 1600 px long edge retains label text while keeping CPU OCR within field-device memory.
    resized = _downscale_for_ocr(image)

    # Convert to grayscale 2D array without destructive blurring filters
    return cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)

