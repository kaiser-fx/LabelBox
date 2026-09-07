import json
import logging
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Lazy singleton for EasyOCR Reader
_reader = None


@dataclass
class OCRBlock:
    text: str
    confidence: float
    bounding_box: list[list[int]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def bounding_box_json(self) -> str:
        return json.dumps(self.bounding_box)


def get_ocr_reader():
    """Lazy initialize and return EasyOCR Reader singleton."""
    global _reader
    if _reader is None:
        try:
            import easyocr
            import torch

            use_gpu = torch.cuda.is_available()
            logger.info("Initializing EasyOCR reader (en, gpu=%s)...", use_gpu)
            _reader = easyocr.Reader(["en"], gpu=use_gpu)
        except Exception as e:
            logger.error("Failed to initialize EasyOCR reader: %s", e)
            raise
    return _reader


def extract_text(image: np.ndarray | str | bytes) -> list[OCRBlock]:
    """Extract text blocks and bounding boxes using EasyOCR.
    Never crashes the caller — returns an empty list if extraction fails.
    """
    try:
        reader = get_ocr_reader()
        raw_results = reader.readtext(image)

        blocks: list[OCRBlock] = []
        for bbox, text, prob in raw_results:
            clean_text = text.strip() if isinstance(text, str) else ""
            if not clean_text:
                continue

            # Convert numpy/float coordinates into standard python ints
            clean_bbox = [[int(pt[0]), int(pt[1])] for pt in bbox]
            blocks.append(
                OCRBlock(
                    text=clean_text,
                    confidence=float(round(prob, 4)),
                    bounding_box=clean_bbox,
                )
            )
        return blocks
    except Exception as e:
        logger.error("OCR extraction failed: %s", e, exc_info=True)
        return []
