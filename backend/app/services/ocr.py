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


def sort_blocks_reading_order(blocks: list[OCRBlock]) -> list[OCRBlock]:
    """Sort OCR blocks into natural reading order: top-to-bottom, line-by-line, left-to-right."""
    if not blocks:
        return []

    def get_cy(b: OCRBlock) -> float:
        ys = [pt[1] for pt in b.bounding_box]
        return (min(ys) + max(ys)) / 2.0 if ys else 0.0

    def get_h(b: OCRBlock) -> int:
        ys = [pt[1] for pt in b.bounding_box]
        return max(ys) - min(ys) if ys else 20

    # Median height of blocks with valid non-zero height
    heights = [get_h(b) for b in blocks if get_h(b) > 0]
    med_h = sorted(heights)[len(heights) // 2] if heights else 20
    line_thresh = max(8, med_h * 0.35)

    # Sort initially by vertical center (cy) and left-x
    sorted_y = sorted(
        blocks,
        key=lambda b: (
            get_cy(b),
            min((pt[0] for pt in b.bounding_box), default=0),
        ),
    )

    lines: list[list[OCRBlock]] = []
    for b in sorted_y:
        cy = get_cy(b)
        placed = False
        for line in lines:
            line_cy = sum(get_cy(item) for item in line) / len(line)
            if abs(cy - line_cy) < line_thresh:
                line.append(b)
                placed = True
                break
        if not placed:
            lines.append([b])

    # Sort each horizontal line left-to-right
    result: list[OCRBlock] = []
    for line in lines:
        line.sort(key=lambda b: min((pt[0] for pt in b.bounding_box), default=0))
        result.extend(line)
    return result



def extract_text(image: np.ndarray | str | bytes) -> list[OCRBlock]:
    """Extract text blocks and bounding boxes using EasyOCR.
    Never crashes the caller — returns an empty list if extraction fails.
    Supports sideways/multi-orientation packaging by auto-recovering rotated panels.
    """
    try:
        reader = get_ocr_reader()
        raw_results = reader.readtext(image)

        def _to_blocks(raw) -> list[OCRBlock]:
            blks: list[OCRBlock] = []
            for bbox, text, prob in raw:
                clean_text = text.strip() if isinstance(text, str) else ""
                if not clean_text:
                    continue
                clean_bbox = [[int(pt[0]), int(pt[1])] for pt in bbox]
                blks.append(
                    OCRBlock(
                        text=clean_text,
                        confidence=float(round(prob, 4)),
                        bounding_box=clean_bbox,
                    )
                )
            return blks

        blocks = _to_blocks(raw_results)

        img_arr = image
        if not isinstance(image, np.ndarray):
            import cv2
            if isinstance(image, (bytes, bytearray)):
                nparr = np.frombuffer(image, np.uint8)
                img_arr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            elif isinstance(image, str):
                img_arr = cv2.imread(image)

        # Detect if image is oriented sideways (predominantly 1-2 char fragments from horizontal lines slicing vertical text)
        if isinstance(img_arr, np.ndarray) and len(blocks) >= 12:
            short_count = sum(1 for b in blocks if len(b.text.strip()) <= 2)
            long_count = sum(1 for b in blocks if len(b.text.strip()) >= 4)
            ratio = short_count / len(blocks)

            if ratio > 0.55 and long_count < 8:
                import cv2
                rot_image = cv2.rotate(img_arr, cv2.ROTATE_90_COUNTERCLOCKWISE)
                raw_rot = reader.readtext(rot_image)
                blocks_rot = _to_blocks(raw_rot)
                long_rot = sum(1 for b in blocks_rot if len(b.text.strip()) >= 4)

                if long_rot > long_count:
                    # Keep any meaningful horizontal blocks from original orientation (e.g. NET CONTENT 50 ml)
                    valid_orig = [b for b in blocks if len(b.text.strip()) >= 3 and b.confidence >= 0.15]
                    sorted_rot = sort_blocks_reading_order(blocks_rot)
                    return sorted_rot + valid_orig

        return sort_blocks_reading_order(blocks)
    except Exception as e:
        logger.error("OCR extraction failed: %s", e, exc_info=True)
        return []

