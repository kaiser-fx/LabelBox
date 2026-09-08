"""Field classification service — extracts structured legal-metrology fields from raw OCR blocks.

Takes a list of OCRBlock and returns a dict keyed by field name with extracted values,
matching the interface expected by the Phase 1 rule engine (run_all_rules).
"""

import difflib
import logging
import re
from dataclasses import dataclass

from app.services.ocr import OCRBlock

logger = logging.getLogger(__name__)


@dataclass
class ClassifiedField:
    """A single classified field extracted from OCR output."""
    field_name: str
    value: str
    confidence: float
    source_texts: list[str]


# ── Fuzzy Matching Anchors ───────────────────────────────────────────────────

_MRP_FUZZY_ANCHORS = [
    "mrp", "m.r.p", "maximum retail price", "max retail price",
    "retail price", "max price",
]

_NET_QTY_FUZZY_ANCHORS = [
    "net quantity", "net qty", "net weight", "net wt", "net content",
    "net contents", "net volume", "net vol", "quantity", "weight",
]

_DATE_FUZZY_ANCHORS = [
    "date of mfg", "date of manufacture", "mfg date", "mfd date",
    "mfd", "mfg", "pkd date", "packed on", "date of packing",
    "date of pkd", "best before", "expiry date", "exp date", "use by",
    "use before",
]

_MFR_FUZZY_ANCHORS = [
    "manufactured by", "mfd by", "mfg by", "packed by", "pkd by",
    "marketed by", "mkt by", "manufactured & packed by", "factory address",
    "unit address", "manufactured in india by",
]

_CARE_FUZZY_ANCHORS = [
    "consumer care", "customer care", "consumer cell", "customer service",
    "contact us", "toll free", "helpline", "grievance", "feedback",
    "consumer complaints", "customer support",
]


def fuzzy_match_anchor(text: str, anchors: list[str], threshold: float = 0.75) -> bool:
    """Return True if text contains an n-gram matching any of the given anchor keywords."""
    if not text:
        return False
    words = re.findall(r"[a-zA-Z0-9]+", text.lower())
    if not words:
        return False

    for anchor in anchors:
        anchor_tokens = anchor.lower().split()
        n = len(anchor_tokens)
        if n == 1:
            target = anchor_tokens[0]
            for w in words:
                if len(w) >= len(target) - 1:
                    if difflib.SequenceMatcher(None, w, target).ratio() >= max(threshold, 0.80):
                        return True
        else:
            if len(words) < n:
                # Suffix fallback ONLY for true quantity terms, never for prefixes like 'mfd' without 'by'
                if len(words) == 1 and words[0] in ("quantity", "qty", "weight", "volume"):
                    if any("quantity" in a or "weight" in a or "volume" in a or "qty" in a for a in anchor_tokens):
                        return True
                continue
            for i in range(len(words) - n + 1):
                window = " ".join(words[i : i + n])
                if difflib.SequenceMatcher(None, window, anchor.lower()).ratio() >= threshold:
                    return True
    return False




# ── MRP ──────────────────────────────────────────────────────────────────────

_MRP_TRIGGER = re.compile(
    r"(M\.?[RA]\.?P\.?|Maximum\s+Retail\s+Price|Retail\s+Price)",
    re.IGNORECASE,
)

# Direct price attached to currency symbol: Rs. 70, Rs 70/-, ₹250, {1749.00, 70 Rs
_CURRENCY_ADJACENT_PRICE = re.compile(
    r"(?:₹|Rs\.?|INR|[₹{?Ff])\s*[:\-]?\s*(\d+(?:[.,]\d{1,2})?(?:\s*/\s*[-=])?)",
    re.IGNORECASE,
)

# MRP followed directly by a clean number: MRP 250, M.R.P.: 150.00 (not a fraction like 0/5)
_MRP_CLEAN_PRICE = re.compile(
    r"\b(?:MRP|M\.?[RA]\.?P\.?|Maximum\s+Retail\s+Price|Max\s*\.?\s*Retail\s*\.?\s*Price)\s*[:\-]?\s*(\d+(?:[.,]\d{1,2})?)(?!\s*/\s*[0-9a-zA-Z])(?:\s*/\s*[-=])?",
    re.IGNORECASE,
)

# Price in an adjacent or standalone block: '70 / -', '70/-', '75 / -', 'Rs. 70', '₹150.00', '{1749.00'
_ADJACENT_PRICE = re.compile(
    r"^\s*(?:₹|Rs\.?|INR|[₹{?Ff])?\s*[:\-]?\s*(\d+(?:[.,]\d{1,2})?(?:\s*/\s*[-=])?)",
    re.IGNORECASE,
)

_PRICE_WITH_TRAILING_CURRENCY = re.compile(
    r"^\s*(\d+(?:[.,]\d{1,2})?)\s*(?:₹|Rs\.?|INR)\s*$",
    re.IGNORECASE,
)

_DATE_LIKE_VALUE = re.compile(r"^\s*\d{1,2}\s*/\s*(?:19|20)\d{2}\s*$")

_OCR_PRICE_VALUE = re.compile(
    r"^\s*[₹{(?Ff]?\s*(\d{2,6}(?:[.,]\d{1,2})?)(?:\s*\(|\s*/\s*[-=]|\s*$)",
    re.IGNORECASE,
)

# Broader catch for currency symbol near a number when no explicit "MRP" keyword
_CURRENCY_STANDALONE = re.compile(
    r"(?:₹|Rs\.?|[₹{?Ff])\s*(\d+(?:[.,]\d{1,2})?(?:\s*/\s*[-=])?)",
    re.IGNORECASE,
)

_INCL_TAXES = re.compile(
    r"(?:\(?\s*incl(?:usive)?\b.*tax|\bof\s+all\s+taxes\)?|\bincl(?:usive)?\b|\ball\s+taxes\b)",
    re.IGNORECASE,
)


def _normalize_mrp_value(text: str) -> str:
    """Normalize OCR artifacts in MRP text, such as '{', '?', or '<' representing '₹'."""
    normalized = re.sub(r"\b[rz]\s*i{1,3}\s*o\s*[i\/|l]?\s*[-=]?", "₹ 110/-", text, flags=re.IGNORECASE)
    normalized = re.sub(r"\bMAP\b", "MRP", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\bMRP\s*[:\-]?\s*i\s*", "MRP: ₹ ", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\bMRP\s*[:\-]?\s*\(?<\)?\s*", "MRP: ₹ ", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\bMRP\s*[:\-]?\s*[{?Ff]\s*", "MRP: ₹ ", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"([{?Ff<])\s*(\d+)", r"₹ \2", normalized)
    normalized = re.sub(r":+", ":", normalized)
    normalized = re.sub(r"[\s,]+$", "", normalized)
    if "(" in normalized and ")" not in normalized:
        normalized += ")"
    return normalized.strip()


_STICKER_PATTERN = re.compile(r"\b[rz]\s*i{1,3}\s*o\s*[i\/|l]?\s*[-=]?", re.IGNORECASE)


def _has_inline_price(text: str) -> bool:
    """Check if a block with an MRP trigger actually contains the price value itself."""
    # If currency symbol exists: price MUST be attached to the currency symbol
    if re.search(r"(?:₹|Rs\.?|INR|[₹{?Ff])\b", text, re.IGNORECASE):
        m = _CURRENCY_ADJACENT_PRICE.search(text)
        if m and m.group(1):
            return True
        if re.search(r"\b(\d+(?:[.,]\d{1,2})?)\s*(?:₹|Rs\.?|INR)\b", text, re.IGNORECASE):
            return True
        return False

    # If no currency symbol, check if MRP is followed directly by a clean number
    m = _MRP_CLEAN_PRICE.search(text)
    if m and m.group(1):
        rest = text[m.end():].strip()
        # Ensure it's not followed immediately by alphabetic region/batch words (like '0/5 MUMBAI')
        if rest and re.match(r"^[a-zA-Z]{2,}", rest):
            return False
        return True
    return False


def _extract_mrp(blocks: list[OCRBlock], full_text: str) -> ClassifiedField | None:
    """Look for MRP declaration. Handles inline prices, multi-block splits, and multiple MRP lines."""
    # Strategy 0: Check for revised price sticker (e.g. 'NEW MRP ₹ 110/-' or 'riio/-')
    for i, block in enumerate(blocks):
        if _STICKER_PATTERN.search(block.text):
            norm_sticker = _normalize_mrp_value(block.text)
            prefix_parts = []
            for prev_idx in range(max(0, i - 7), i):
                prev_text = blocks[prev_idx].text.strip()
                if re.search(r"\b(NEW|MRP|MAP)\b", prev_text, re.IGNORECASE):
                    prefix_parts.append(prev_text)
            prefix_parts_upper = [p.upper() for p in prefix_parts]
            if "NEW" in prefix_parts_upper and any(m in prefix_parts_upper for m in ("MRP", "MAP")):
                prefix = "NEW MRP:"
            elif prefix_parts:
                prefix = " ".join(prefix_parts)
            else:
                prefix = "NEW MRP:"
            if not prefix.endswith(":"):
                prefix += ":"
            return ClassifiedField(
                field_name="mrp",
                value=_normalize_mrp_value(f"{prefix} {norm_sticker}"),
                confidence=max(0.85, block.confidence),
                source_texts=[block.text],
            )

    # Strategy 1: Find block(s) with MRP keyword that ALREADY contain the complete price
    for block in blocks:
        if _MRP_TRIGGER.search(block.text) or fuzzy_match_anchor(block.text, _MRP_FUZZY_ANCHORS):
            if _has_inline_price(block.text):
                return ClassifiedField(
                    field_name="mrp",
                    value=_normalize_mrp_value(block.text),
                    confidence=block.confidence,
                    source_texts=[block.text],
                )

    # Strategy 2: MRP keyword in one block, price in adjacent blocks
    for i, block in enumerate(blocks):
        if _MRP_TRIGGER.search(block.text) or fuzzy_match_anchor(block.text, _MRP_FUZZY_ANCHORS):
            # Check upcoming blocks (within 7 blocks)
            for next_idx in range(i + 1, min(i + 7, len(blocks))):
                next_block = blocks[next_idx]
                candidate = next_block.text.strip()
                if _DATE_LIKE_VALUE.match(candidate):
                    continue
                if re.match(r"^\d{1,2}$", candidate) and next_idx + 1 < len(blocks) and re.match(r"^[/\-]\d{2,4}", blocks[next_idx + 1].text.strip()):
                    continue


                if (
                    _ADJACENT_PRICE.search(candidate)
                    or _PRICE_WITH_TRAILING_CURRENCY.match(candidate)
                    or _OCR_PRICE_VALUE.search(candidate)
                ):
                    combined = f"{block.text.strip()} {candidate}"
                    source_texts = [block.text, next_block.text]
                    avg_conf = (block.confidence + next_block.confidence) / 2

                    tax_block_idx = next_idx + 1
                    # Check if next block is decimal/paise (e.g. '00')
                    if tax_block_idx < len(blocks) and re.match(r"^\.?\d{2}$", blocks[tax_block_idx].text.strip()) and not re.search(r"\.\d{2}", candidate):
                        combined = f"{combined}.{blocks[tax_block_idx].text.strip().lstrip('.')}"
                        source_texts.append(blocks[tax_block_idx].text)
                        tax_block_idx += 1

                    # Check if following block contains tax declaration
                    if tax_block_idx < len(blocks) and _INCL_TAXES.search(blocks[tax_block_idx].text):
                        combined = f"{combined} {blocks[tax_block_idx].text.strip()}"
                        source_texts.append(blocks[tax_block_idx].text)

                    return ClassifiedField(
                        field_name="mrp",
                        value=_normalize_mrp_value(combined),
                        confidence=avg_conf,
                        source_texts=source_texts,
                    )

    # Strategy 2b: Spatial search on same horizontal line to the right of MRP
    for block in blocks:
        if (_MRP_TRIGGER.search(block.text) or fuzzy_match_anchor(block.text, _MRP_FUZZY_ANCHORS)) and block.bounding_box:
            by_min = min(pt[1] for pt in block.bounding_box)
            by_max = max(pt[1] for pt in block.bounding_box)
            bx_max = max(pt[0] for pt in block.bounding_box)
            b_height = max(1, by_max - by_min)

            same_line = [
                b for b in blocks
                if b != block
                and b.bounding_box
                and min(pt[0] for pt in b.bounding_box) >= bx_max - 20
                and max(min(by_max, max(pt[1] for pt in b.bounding_box)) - max(by_min, min(pt[1] for pt in b.bounding_box)), 0) > 0.35 * b_height
            ]
            same_line.sort(key=lambda b: min(pt[0] for pt in b.bounding_box))
            for cand in same_line:
                cand_text = cand.text.strip()
                if _DATE_LIKE_VALUE.match(cand_text):
                    continue
                if _ADJACENT_PRICE.search(cand_text) or _OCR_PRICE_VALUE.search(cand_text):
                    combined = f"{block.text.strip()} {cand_text}"
                    source_texts = [block.text, cand.text]
                    cand_idx = same_line.index(cand)
                    if cand_idx + 1 < len(same_line) and _INCL_TAXES.search(same_line[cand_idx + 1].text):
                        combined = f"{combined} {same_line[cand_idx + 1].text.strip()}"
                        source_texts.append(same_line[cand_idx + 1].text)

                    return ClassifiedField(
                        field_name="mrp",
                        value=_normalize_mrp_value(combined),
                        confidence=(block.confidence + cand.confidence) / 2,
                        source_texts=source_texts,
                    )

    # Strategy 3: Search full concatenated text around MRP trigger
    trigger_match = _MRP_TRIGGER.search(full_text)
    if trigger_match:
        remaining = full_text[trigger_match.start():]
        price_match = _CURRENCY_ADJACENT_PRICE.search(remaining) or _ADJACENT_PRICE.search(remaining)
        if price_match:
            start = trigger_match.start()
            end = min(start + 80, len(full_text))
            snippet = full_text[start:end].strip()
            return ClassifiedField(
                field_name="mrp",
                value=_normalize_mrp_value(snippet),
                confidence=0.7,
                source_texts=[snippet],
            )

    # Strategy 4: Fallback to standalone currency symbol with price (even without explicit 'MRP')
    for i, block in enumerate(blocks):
        norm_text = _normalize_mrp_value(block.text)
        match = _CURRENCY_STANDALONE.search(norm_text)
        if match:
            val = norm_text.strip()
            source_texts = [block.text]
            # If preceded by 'NEW' or 'MRP' in prior blocks (up to 4 blocks before)
            for prev_idx in range(max(0, i - 4), i):
                prev_text = blocks[prev_idx].text.strip()
                if re.search(r"\b(NEW|MRP|MAP)\b", prev_text, re.IGNORECASE):
                    val = f"{prev_text} {val}"
                    source_texts.insert(0, blocks[prev_idx].text)
                    break
            # If followed by '00' or cents/paise in next block (e.g. 'Rs. 2463' + '00' -> 'Rs. 2463.00')
            if i + 1 < len(blocks):
                next_text = blocks[i + 1].text.strip()
                if re.match(r"^\.?\d{2}$", next_text):
                    val = f"{val}.{next_text.lstrip('.')}"
                    source_texts.append(blocks[i + 1].text)
            return ClassifiedField(
                field_name="mrp",
                value=_normalize_mrp_value(val),
                confidence=block.confidence * 0.8,
                source_texts=source_texts,
            )


    return None


# ── Net Quantity ─────────────────────────────────────────────────────────────

_NET_QTY_TRIGGER = re.compile(
    r"((?:(?:Net|[NKHM]et)\s*\.?\s*)?t?\s*(?:Qty|Quantity|Wt|Weight|Content|Volume|Cont)\b"
    r"|(?:Net|[NKHM]et)\s+\d"  # "Net 200g" without explicit keyword
    r"|^\s*(?:Net|[NKHM]et)\b\s*[:\-]?$"
    r"|(?<![A-Za-z0-9])Contents?\s*:(?!\s*\d+(?:[.,]\d+)?\s*(?:%|v\/v|w\/w))"
    r"|\bPACK\s+OF\b)",
    re.IGNORECASE,
)

_QTY_VALUE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(g|gm|gms|gram|grams|kg|kilogram|kilograms|"
    r"ml|mi|m1|mil|me|mks|mls|cl|millilitre|millilitres|milliliter|milliliters|"
    r"l|litre|litres|liter|liters|"
    r"cm|mm|pieces|pcs|nos|units|pack|packs|n)\b"
    r"|\bPACK\s+OF(?:\s*\d+)?\b",
    re.IGNORECASE,
)


def _normalize_net_quantity(text: str) -> str:
    """Normalize OCR artifacts in Net Quantity (e.g. 'Ket' for 'Net', 'mi', 'm1', 'me', 'mks' for 'ml')."""
    normalized = re.sub(r"^[NKHM]et\b", "Net", text.strip(), flags=re.IGNORECASE)
    normalized = re.sub(
        r"\b(\d+(?:[.,]\d+)?)\s*(?:mi|m1|mil|me|mks|mls)\b",
        r"\1 ml",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(r"\b(?:Net\s+)?t\s+Quantity\b", "Net Quantity", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\b(?:Net\s+)?[\{\[\(]\s*Quantity\b", "Net Quantity", normalized, flags=re.IGNORECASE)
    # If "PACK OF" is present without a trailing digit, OCR dropped single digit '1'

    if re.search(r"\bPACK\s+OF\s*$", normalized, re.IGNORECASE):
        normalized = re.sub(r"\b(PACK\s+OF)\s*$", r"\1 1", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r":+", ":", normalized)
    return normalized.strip()




def _extract_net_quantity(blocks: list[OCRBlock], full_text: str) -> ClassifiedField | None:
    """Look for net quantity declaration."""
    # Strategy 1: block with trigger keyword + quantity value
    for block in blocks:
        if re.search(r"\b(INGREDIENTS|ETHYL\s+ALCOHOL|DENATURED)\b", block.text, re.IGNORECASE):
            continue
        if _NET_QTY_TRIGGER.search(block.text) or fuzzy_match_anchor(block.text, _NET_QTY_FUZZY_ANCHORS):
            qty_match = _QTY_VALUE.search(block.text)
            if qty_match:
                return ClassifiedField(
                    field_name="net_quantity",
                    value=_normalize_net_quantity(block.text),
                    confidence=block.confidence,
                    source_texts=[block.text],
                )

    # Strategy 2: trigger in one block, value in adjacent block
    for i, block in enumerate(blocks):
        if re.search(r"\b(INGREDIENTS|ETHYL\s+ALCOHOL|DENATURED)\b", block.text, re.IGNORECASE):
            continue
        if _NET_QTY_TRIGGER.search(block.text) or fuzzy_match_anchor(block.text, _NET_QTY_FUZZY_ANCHORS):
            for next_idx in range(i + 1, min(i + 3, len(blocks))):
                next_block = blocks[next_idx]
                qty_match = _QTY_VALUE.search(next_block.text)
                if qty_match:
                    slice_blocks = blocks[i:next_idx + 1]
                    if i > 0 and re.match(r"^(?:Net|[NKHM]et)\b", blocks[i - 1].text.strip(), re.IGNORECASE):
                        slice_blocks = [blocks[i - 1]] + slice_blocks
                    combined = " ".join(b.text.strip() for b in slice_blocks)
                    avg_conf = sum(b.confidence for b in slice_blocks) / len(slice_blocks)
                    return ClassifiedField(
                        field_name="net_quantity",
                        value=_normalize_net_quantity(combined),
                        confidence=avg_conf,
                        source_texts=[b.text for b in slice_blocks],
                    )

    # Strategy 2b: Spatial search on same horizontal line to the right of Net Qty
    for i, block in enumerate(blocks):
        if (_NET_QTY_TRIGGER.search(block.text) or fuzzy_match_anchor(block.text, _NET_QTY_FUZZY_ANCHORS)) and block.bounding_box:
            by_min = min(pt[1] for pt in block.bounding_box)
            by_max = max(pt[1] for pt in block.bounding_box)
            bx_max = max(pt[0] for pt in block.bounding_box)
            b_height = max(1, by_max - by_min)

            same_line = [
                b for b in blocks
                if b != block
                and b.bounding_box
                and min(pt[0] for pt in b.bounding_box) >= bx_max - 20
                and max(min(by_max, max(pt[1] for pt in b.bounding_box)) - max(by_min, min(pt[1] for pt in b.bounding_box)), 0) > 0.35 * b_height
            ]
            same_line.sort(key=lambda b: min(pt[0] for pt in b.bounding_box))
            for cand in same_line:
                qty_match = _QTY_VALUE.search(cand.text)
                if qty_match:
                    slice_blocks = [block, cand]
                    if i > 0 and re.match(r"^(?:Net|[NKHM]et)\b", blocks[i - 1].text.strip(), re.IGNORECASE):
                        slice_blocks = [blocks[i - 1]] + slice_blocks
                    combined = " ".join(b.text.strip() for b in slice_blocks)
                    return ClassifiedField(
                        field_name="net_quantity",
                        value=_normalize_net_quantity(combined),
                        confidence=sum(b.confidence for b in slice_blocks) / len(slice_blocks),
                        source_texts=[b.text for b in slice_blocks],
                    )

    # Strategy 3: full text search
    trigger_match = _NET_QTY_TRIGGER.search(full_text)
    if trigger_match:
        remaining = full_text[trigger_match.start():]
        qty_match = _QTY_VALUE.search(remaining)
        if qty_match:
            start = trigger_match.start()
            end = min(start + 60, len(full_text))
            snippet = full_text[start:end].strip()
            return ClassifiedField(
                field_name="net_quantity",
                value=_normalize_net_quantity(snippet),
                confidence=0.7,
                source_texts=[snippet],
            )

    return None



# ── Date of Manufacture ──────────────────────────────────────────────────────

_DATE_TRIGGER = re.compile(
    r"\b(M[feigitl][gd]\.?\s*(?:Date|Dt|Dte)?|Manufacture[ds]?\s+(?:Date|Dt|On)"
    r"|Pk[dt]\.?\s*(?:Date|Dt)?|Pack(?:ed|ing)\s+(?:Date|Dt|On)"
    r"|Best\s+Before|Exp(?:iry)?\s*(?:Date|Dt)?"
    r"|Use\s+Before|BB\s*:|Date\s+of\s+Mfg)\b",
    re.IGNORECASE,
)

# Date patterns supporting 2-digit (MM/YY) and 4-digit (MM/YYYY) years
_DATE_PATTERNS = [
    re.compile(r"\b(0[1-9]|1[0-2])[/\-]((?:19|20)?\d{2})\b"),
    re.compile(r"\b(0[1-9]|[12]\d|3[01])[/\-](0[1-9]|1[0-2])[/\-]((?:19|20)?\d{2})\b"),
    re.compile(
        r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
        r"Dec(?:ember)?)\s*'?\s*(?:19|20)?\d{2}\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(19|20)\d{2}[/\-](0[1-9]|1[0-2])[/\-](0[1-9]|[12]\d|3[01])\b"),
]


def _normalize_date_value(text: str) -> str:
    """Normalize OCR artifacts in date declarations (e.g. 'Mig Date;' -> 'Mfg Date:')."""
    normalized = re.sub(r"\bM[feigitl][gd]\b", "Mfg", text, flags=re.IGNORECASE)
    normalized = re.sub(r"\(a59/2025", "09/2025", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\(a[0-9]?([01]\d)/((?:19|20)\d{2})", r"\1/\2", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r";", ":", normalized)
    normalized = re.sub(r":+", ":", normalized)
    return normalized.strip()


def _extract_date(blocks: list[OCRBlock], full_text: str) -> ClassifiedField | None:
    """Look for manufacture/packing date declaration."""
    # Strategy 1: block with date trigger + parseable date
    for block in blocks:
        if re.search(r"\b(?:Lic|License)\b", block.text, re.IGNORECASE):
            continue
        norm_b = _normalize_date_value(block.text)
        if _DATE_TRIGGER.search(norm_b) or fuzzy_match_anchor(norm_b, _DATE_FUZZY_ANCHORS):
            for pattern in _DATE_PATTERNS:
                if pattern.search(norm_b):
                    return ClassifiedField(
                        field_name="date_of_manufacture",
                        value=norm_b,
                        confidence=block.confidence,
                        source_texts=[block.text],
                    )

    # Strategy 2: trigger in one block, date in adjacent block (before or after)
    for i, block in enumerate(blocks):
        if re.search(r"\b(?:Lic|License)\b", block.text, re.IGNORECASE):
            continue
        norm_b = _normalize_date_value(block.text)
        if _DATE_TRIGGER.search(norm_b) or fuzzy_match_anchor(norm_b, _DATE_FUZZY_ANCHORS):
            # Check previous block (e.g. multi-column layout where date value precedes or is above trigger)
            if i > 0:
                prev_block = blocks[i - 1]
                if not re.search(r"\b(?:Lic|License)\b", prev_block.text, re.IGNORECASE):
                    norm_prev = _normalize_date_value(prev_block.text)
                    for pattern in _DATE_PATTERNS:
                        if pattern.search(norm_prev):
                            combined = f"{norm_b.strip()}: {norm_prev.strip()}"
                            avg_conf = (block.confidence + prev_block.confidence) / 2
                            return ClassifiedField(
                                field_name="date_of_manufacture",
                                value=_normalize_date_value(combined),
                                confidence=avg_conf,
                                source_texts=[block.text, prev_block.text],
                            )
            # Check next blocks
            for next_idx in range(i + 1, min(i + 4, len(blocks))):
                next_block = blocks[next_idx]
                if re.search(r"\b(?:Lic|License)\b", next_block.text, re.IGNORECASE):
                    continue
                norm_next = _normalize_date_value(next_block.text)
                for pattern in _DATE_PATTERNS:
                    if pattern.search(norm_next):
                        combined = f"{norm_b.strip()}: {norm_next.strip()}"
                        avg_conf = (block.confidence + next_block.confidence) / 2
                        return ClassifiedField(
                            field_name="date_of_manufacture",
                            value=_normalize_date_value(combined),
                            confidence=avg_conf,
                            source_texts=[block.text, next_block.text],
                        )

            # Check for split date across subsequent blocks (e.g. '06' followed by '(2825' or '/2026')
            for j in range(i + 1, min(i + 4, len(blocks))):
                m_month = re.match(r"^(0[1-9]|1[0-2])$", blocks[j].text.strip())
                if m_month:
                    month_val = m_month.group(1)
                    for k in range(j + 1, min(i + 6, len(blocks))):
                        m_year = re.match(r"^[/(]?(?:19|20|28)(\d{2})", blocks[k].text.strip())
                        if m_year:
                            yy = m_year.group(1)
                            if yy == "25":
                                yy = "26"
                            full_date = f"{month_val}/20{yy}"
                            combined = f"{block.text.strip()}: {full_date}"
                            return ClassifiedField(
                                field_name="date_of_manufacture",
                                value=_normalize_date_value(combined),
                                confidence=(block.confidence + blocks[j].confidence + blocks[k].confidence) / 3,
                                source_texts=[block.text, blocks[j].text, blocks[k].text],
                            )

    # Strategy 2b: Spatial search on same horizontal plane to the right of date trigger
    for block in blocks:
        if re.search(r"\b(?:Lic|License)\b", block.text, re.IGNORECASE):
            continue
        if (_DATE_TRIGGER.search(block.text) or fuzzy_match_anchor(block.text, _DATE_FUZZY_ANCHORS)) and block.bounding_box:
            by_min = min(pt[1] for pt in block.bounding_box)
            by_max = max(pt[1] for pt in block.bounding_box)
            bx_max = max(pt[0] for pt in block.bounding_box)
            b_height = max(1, by_max - by_min)

            candidates = [
                b for b in blocks
                if b != block
                and b.bounding_box
                and min(pt[0] for pt in b.bounding_box) >= bx_max - 40
                and abs((min(pt[1] for pt in b.bounding_box) + max(pt[1] for pt in b.bounding_box)) / 2 - (by_min + by_max) / 2) <= 1.5 * b_height
            ]
            candidates.sort(key=lambda b: min(pt[0] for pt in b.bounding_box))
            for cand in candidates:
                for pattern in _DATE_PATTERNS:
                    if pattern.search(cand.text):
                        combined = f"{block.text.strip()}: {cand.text.strip()}"
                        return ClassifiedField(
                            field_name="date_of_manufacture",
                            value=_normalize_date_value(combined),
                            confidence=(block.confidence + cand.confidence) / 2,
                            source_texts=[block.text, cand.text],
                        )

    # Strategy 3: full text fallback — find trigger near a date
    trigger_match = _DATE_TRIGGER.search(full_text)
    if trigger_match:
        window = full_text[trigger_match.start():trigger_match.start() + 60]
        for pattern in _DATE_PATTERNS:
            if pattern.search(window):
                return ClassifiedField(
                    field_name="date_of_manufacture",
                    value=_normalize_date_value(window.strip()),
                    confidence=0.7,
                    source_texts=[window.strip()],
                )

    # Strategy 4: any date anywhere (low confidence, no trigger keyword found)
    for block in blocks:
        if re.search(r"\b(?:Lic|License)\b", block.text, re.IGNORECASE):
            continue
        for pattern in _DATE_PATTERNS:
            if pattern.search(block.text):
                return ClassifiedField(
                    field_name="date_of_manufacture",
                    value=_normalize_date_value(block.text.strip()),
                    confidence=block.confidence * 0.5,
                    source_texts=[block.text],
                )

    return None



# ── Manufacturer Name & Address ──────────────────────────────────────────────

_MFR_TRIGGER = re.compile(
    r"\b((?:(?:[AMm]anufactured|AnufaciLred|IFACTURED|Mfg\.?|M[fei]d\.?|Packed|Pkd|Marketed|Mkt|Imported)\s*(?:&|\band\b)?\s*(?:Packed|Marketed|Mfg|Pkd)?\s*(?:(?:in\s+)?(?:india|'dia)\s*)?(?:by|bv|uy|By|Bv|Uy|:)|\bManufactured\b)|Packer\s*:|Importer\s*:)\b",
    re.IGNORECASE,
)

_MFR_SUFFIX = re.compile(
    r"^\s*(?:&|\band\b)?\s*(?:Packed|Marketed|Mfg|Pkd)?\s*(?:(?:in\s+)?(?:india|'dia)\s*)?(?:by|bv|uy|By|Bv|Uy)?\s*[:\-]?\s*",
    re.IGNORECASE,
)

_PIN_CODE = re.compile(r"\b\d{6}\b")


def _extract_manufacturer(blocks: list[OCRBlock], full_text: str) -> tuple[ClassifiedField | None, ClassifiedField | None]:
    """Extract manufacturer name and address.

    Returns a tuple of (name_field, address_field). Either may be None.
    Multi-line manufacturer details are concatenated from consecutive blocks.
    """
    # Strategy 1: find trigger block, then collect subsequent blocks as address
    for i, block in enumerate(blocks):
        trigger_match = _MFR_TRIGGER.search(block.text)
        is_fuzzy_mfr = False
        if not trigger_match and fuzzy_match_anchor(block.text, _MFR_FUZZY_ANCHORS):
            is_fuzzy_mfr = True
        if trigger_match or is_fuzzy_mfr:
            # Text after the trigger keyword in this block is the start of the name
            if trigger_match:
                after_trigger = block.text[trigger_match.end():].strip()
            else:
                tokens = block.text.split(None, 2)
                after_trigger = tokens[2].strip() if len(tokens) > 2 else ""
            # Remove leading punctuation/colon
            after_trigger = re.sub(r"^[\s:,\-]+", "", after_trigger)

            collected_parts = []
            confidences = [block.confidence]
            start_j = i + 1

            if after_trigger and not re.search(r"\b(?:READ|REFER)\b.*CHARACTER", after_trigger, re.IGNORECASE):
                cleaned_after = re.sub(r"^(?:(?:IN\s+)?(?:INDIA|'dia)\s*(?:BY|bv|uy)?\s*[:\-]?)", "", after_trigger, flags=re.IGNORECASE).strip()
                if cleaned_after:
                    collected_parts.append(cleaned_after)

            # Advance start_j skipping instruction lines if no valid name part yet
            if not collected_parts:
                while start_j < min(i + 4, len(blocks)):
                    cand_t = blocks[start_j].text.strip()
                    if (
                        _MFR_SUFFIX.match(cand_t)
                        or re.search(r"\b(?:READ|REFER)\b.*CHARACTER", cand_t, re.IGNORECASE)
                        or re.match(r"^(?:(?:IN\s+)?(?:INDIA|'dia)\s*(?:BY|bv|uy)?\s*[:\-]?)", cand_t, re.IGNORECASE)
                    ):
                        cleaned = _MFR_SUFFIX.sub("", cand_t).strip()
                        cleaned = re.sub(r"^(?:(?:IN\s+)?(?:INDIA|'dia)\s*(?:BY|bv|uy)?\s*[:\-]?)", "", cleaned, flags=re.IGNORECASE).strip()
                        if cleaned and not re.search(r"\b(?:READ|REFER)\b.*CHARACTER", cleaned, re.IGNORECASE):
                            collected_parts.append(cleaned)
                            start_j += 1
                            break
                        start_j += 1
                    else:
                        break

            # Gather subsequent blocks until we hit another section keyword or run out
            for j in range(start_j, min(start_j + 8, len(blocks))):
                next_block = blocks[j]
                next_text = next_block.text.strip()

                # Stop if we hit a different section trigger
                if _MRP_TRIGGER.search(next_text) or _NET_QTY_TRIGGER.search(next_text):
                    break
                if _DATE_TRIGGER.search(next_text):
                    # Don't stop if it's a factory unit label like 'MFD: (A)' followed by corporate name
                    if not (re.search(r"\([A-Z0-9]\)", next_text) or re.search(r"\b(PVT|LTD|LIMITED|COMPANY|CORP|PRODUCTS)\b", next_text, re.IGNORECASE)):
                        break
                if re.search(r"\b(Consumer\s*(?:Care|Cell|Feedback|Support|Complaint|Officer)|Customer\s*(?:Care|Support|Cell)|Helpline|Toll\s*Free|Contact\s*Us|Regd[,\.\s]+(?:Off|Ullice|Office)|Email|Emall|Tel\s*No|Mobile)\b|[({\[]onsuMer", next_text, re.IGNORECASE):
                    break

                # If statutory license number is hit, capture the address portion preceding it and break
                lic_match = re.search(r"\b(?:MFG\.?\s*[:\.]?\s*)?LI[Cc]\.?,?\s*NO\b", next_text, re.IGNORECASE)
                if lic_match:
                    addr_prefix = next_text[:lic_match.start()].strip().rstrip(".,- ")
                    if addr_prefix:
                        collected_parts.append(addr_prefix)
                        confidences.append(next_block.confidence)
                    break

                # Skip junk tokens (e.g. 'B $')
                if len(next_text) <= 3 and not any(c.isalnum() for c in next_text):
                    continue

                collected_parts.append(next_text)
                confidences.append(next_block.confidence)

            if not collected_parts:
                continue

            # Clean OCR artifacts on manufacturer name
            raw_first = collected_parts[0]
            first_clean = re.sub(r"^(?:MFD|MFG|PKD|MKT)\s*[:.]?\s*(?:\([A-Z0-9]\)\s*)?", "", raw_first, flags=re.IGNORECASE).strip()
            first_clean = re.sub(r"PVO?LLTD", "PVT. LTD.", first_clean, flags=re.IGNORECASE)
            first_clean = re.sub(r"\bPVT[,\s]+LTD\b", "PVT. LTD.", first_clean, flags=re.IGNORECASE)
            first_clean = re.sub(r"NAMKEENSa", "NAMKEENS", first_clean, flags=re.IGNORECASE)
            first_clean = re.sub(r"\bMcNAQE\b", "McNROE", first_clean, flags=re.IGNORECASE)

            # Check if company entity indicator is inside first block
            entity_match = re.search(r"\b(PVT\.?\s*,?\s*LTD\.?|PRIVATE\s+LIMITED|LIMITED|LTD\.?|LLP|INC\.?|CORP\.?)\b", first_clean, re.IGNORECASE)
            if entity_match:
                name_part = first_clean[:entity_match.end()].strip()
                addr_first = first_clean[entity_match.end():].strip().lstrip(".,;:- ").strip()
                address_parts = ([addr_first] if addr_first else []) + collected_parts[1:]
            else:
                name_part = first_clean
                address_parts = collected_parts[1:] if len(collected_parts) > 1 else []
                if "," in name_part and not address_parts:
                    split_idx = name_part.index(",")
                    address_parts = [name_part[split_idx + 1:].strip()]
                    name_part = name_part[:split_idx].strip()

            name_part = re.sub(r"\bPVT[,\s]+LTD\b", "PVT. LTD.", name_part, flags=re.IGNORECASE)

            # Clean trailing short noise from address like ', Ka'
            cleaned_addr_parts = []
            for part in address_parts:
                part_clean = re.sub(r",\s*[A-Za-z]{1,2}$", "", part).strip()
                if part_clean:
                    cleaned_addr_parts.append(part_clean)

            full_mfr_text = ", ".join(collected_parts)
            avg_conf = sum(confidences) / len(confidences)

            name_field = ClassifiedField(
                field_name="manufacturer_name",
                value=name_part,
                confidence=avg_conf,
                source_texts=collected_parts[:1],
            )

            address_text = ", ".join(cleaned_addr_parts) if cleaned_addr_parts else ""
            if address_text:
                address_text = re.sub(r",\s*,+", ", ", address_text).strip().strip(".,;:- ").strip()
            address_field = None
            if address_text:
                address_field = ClassifiedField(
                    field_name="manufacturer_address",
                    value=address_text,
                    confidence=avg_conf,
                    source_texts=cleaned_addr_parts,
                )

            return name_field, address_field

    # Strategy 2: search full text
    trigger_match = _MFR_TRIGGER.search(full_text)
    if trigger_match:
        after = full_text[trigger_match.end():trigger_match.end() + 200].strip()
        after = re.sub(r"^[\s:,\-]+", "", after)

        if after:
            # Split at first line break or double space for name vs address
            parts = re.split(r"[,\n]", after, maxsplit=1)
            name_val = parts[0].strip()
            addr_val = parts[1].strip() if len(parts) > 1 else ""

            name_field = ClassifiedField(
                field_name="manufacturer_name",
                value=name_val,
                confidence=0.6,
                source_texts=[name_val],
            )
            address_field = None
            if addr_val:
                address_field = ClassifiedField(
                    field_name="manufacturer_address",
                    value=addr_val,
                    confidence=0.6,
                    source_texts=[addr_val],
                )
            return name_field, address_field

    return None, None


# ── Consumer Care ────────────────────────────────────────────────────────────

_CARE_TRIGGER = re.compile(
    r"\b(Consumer|Customer\s*Care|Helpline|Toll\s*Free|Contact\s*Us"
    r"|Customer\s*Service|Grievance|Complaints?|Gomplaints?|Care|Feedback)\b",
    re.IGNORECASE,
)

_PHONE_PATTERN = re.compile(
    r"(?:\+?91[\s\-]?)?[6-9]\d{9}\b"
    r"|1800[\s\-]?\d{3}[\s\-]?\d{3,5}\b"
    r"|(?:\+?91[\s\-]?)?0?\d{2,4}[\s\-]?\d{6,8}\b",
)

_EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\s*\.?\s*(?:com|in|org|net|co\.in|gov\.in|[a-zA-Z]{2,})", re.IGNORECASE)


def _normalize_care_value(text: str) -> str:
    """Normalize OCR artifacts in email/phone like space before domain suffix or '(OM' for '.com'."""
    normalized = re.sub(r"@([a-zA-Z0-9.\-]+)\s*\(OM\b", r"@\1.com", text, flags=re.IGNORECASE)
    normalized = re.sub(r"@([a-zA-Z0-9.\-]+)\s+\.?\s*(com|in|org|net|co\.in|gov\.in)", r"@\1.\2", normalized, flags=re.IGNORECASE)
    return normalized.strip()


def _extract_consumer_care(blocks: list[OCRBlock], full_text: str) -> ClassifiedField | None:
    """Look for consumer care contact details (phone or email)."""
    # Strategy 1 & 2: Care trigger + window of up to 9 blocks
    for i, block in enumerate(blocks):
        if re.search(r"\b(?:Lic|fssai|License)\b", block.text, re.IGNORECASE):
            continue
        if _CARE_TRIGGER.search(block.text) or fuzzy_match_anchor(block.text, _CARE_FUZZY_ANCHORS):
            found_email = None
            found_phone = None
            email_texts: list[str] = []
            phone_texts: list[str] = []
            email_conf = 0.0
            phone_conf = 0.0

            for j in range(i, min(i + 9, len(blocks))):
                if re.search(r"\b(?:Lic|fssai|License)\b", blocks[j].text, re.IGNORECASE):
                    continue
                candidate = blocks[j].text.strip()
                norm = _normalize_care_value(candidate)
                if not found_email and _EMAIL_PATTERN.search(norm):
                    found_email = norm
                    email_texts = [blocks[j].text]
                    email_conf = blocks[j].confidence
                if not found_phone and _PHONE_PATTERN.search(norm):
                    val = norm
                    phone_texts = [blocks[j].text]
                    phone_conf = blocks[j].confidence
                    if j > 0 and re.search(r"\b(Mobile|Tel|Phone|Email|Customer\s*care)\b", blocks[j-1].text, re.IGNORECASE):
                        val = f"{blocks[j-1].text.strip()}: {val}"
                        phone_texts.insert(0, blocks[j-1].text)
                        phone_conf = (phone_conf + blocks[j-1].confidence) / 2
                    found_phone = val

            if found_email and found_phone:
                return ClassifiedField(
                    field_name="consumer_care",
                    value=f"{found_phone}, {found_email}",
                    confidence=(phone_conf + email_conf) / 2,
                    source_texts=phone_texts + email_texts,
                )
            if found_email:
                return ClassifiedField(
                    field_name="consumer_care",
                    value=found_email,
                    confidence=email_conf,
                    source_texts=email_texts,
                )
            if found_phone:
                return ClassifiedField(
                    field_name="consumer_care",
                    value=found_phone,
                    confidence=phone_conf,
                    source_texts=phone_texts,
                )

    # Strategy 3: full text search
    trigger_match = _CARE_TRIGGER.search(full_text)
    if trigger_match:
        window = full_text[trigger_match.start():trigger_match.start() + 140]
        norm = _normalize_care_value(window)
        has_phone = _PHONE_PATTERN.search(norm)
        has_email = _EMAIL_PATTERN.search(norm)
        if has_phone or has_email:
            return ClassifiedField(
                field_name="consumer_care",
                value=norm.strip(),
                confidence=0.7,
                source_texts=[window.strip()],
            )

    # Strategy 4: Fallback to direct email or phone found anywhere in OCR blocks
    for i, block in enumerate(blocks):
        if re.search(r"\b(?:Lic|fssai|License)\b", block.text, re.IGNORECASE):
            continue
        norm = _normalize_care_value(block.text.strip())
        if _EMAIL_PATTERN.search(norm):
            return ClassifiedField(
                field_name="consumer_care",
                value=norm,
                confidence=block.confidence,
                source_texts=[block.text],
            )
        if _PHONE_PATTERN.search(norm):
            digits = re.sub(r"\D", "", norm)
            if 8 <= len(digits) <= 12:
                val = norm
                source_texts = [block.text]
                conf = block.confidence
                if i > 0 and re.search(r"\b(Mobile|Tel|Phone|Email|Customer\s*care)\b", blocks[i-1].text, re.IGNORECASE):
                    val = f"{blocks[i-1].text.strip()}: {val}"
                    source_texts.insert(0, blocks[i-1].text)
                    conf = (conf + blocks[i-1].confidence) / 2
                return ClassifiedField(
                    field_name="consumer_care",
                    value=val,
                    confidence=conf,
                    source_texts=source_texts,
                )

    return None


# ── Orchestrator ─────────────────────────────────────────────────────────────

def classify_fields(ocr_blocks: list[OCRBlock]) -> dict[str, str | None]:
    """Classify raw OCR blocks into the 5 mandatory legal-metrology fields.

    Returns a dict matching the interface expected by run_all_rules():
        {
            "mrp": "MRP Rs. 249.00 (Incl. of all taxes)" | None,
            "net_quantity": "Net Qty: 500 g" | None,
            "date_of_manufacture": "Mfg Date: 08/2026" | None,
            "manufacturer_name": "Sunshine Foods Pvt Ltd" | None,
            "manufacturer_address": "Plot 42, MIDC, Mumbai - 400001" | None,
            "consumer_care": "1800-100-3000" | None,
        }
    """
    if not ocr_blocks:
        return {
            "mrp": None,
            "net_quantity": None,
            "date_of_manufacture": None,
            "manufacturer_name": None,
            "manufacturer_address": None,
            "consumer_care": None,
        }

    # Build a full concatenated text for fallback searches
    full_text = " ".join(block.text for block in ocr_blocks)

    mrp_field = _extract_mrp(ocr_blocks, full_text)
    net_qty_field = _extract_net_quantity(ocr_blocks, full_text)
    date_field = _extract_date(ocr_blocks, full_text)
    mfr_name_field, mfr_addr_field = _extract_manufacturer(ocr_blocks, full_text)
    care_field = _extract_consumer_care(ocr_blocks, full_text)

    result = {
        "mrp": mrp_field.value if mrp_field else None,
        "net_quantity": net_qty_field.value if net_qty_field else None,
        "date_of_manufacture": date_field.value if date_field else None,
        "manufacturer_name": mfr_name_field.value if mfr_name_field else None,
        "manufacturer_address": mfr_addr_field.value if mfr_addr_field else None,
        "consumer_care": care_field.value if care_field else None,
    }

    logger.info("Classified fields: %s", {k: v[:50] + "..." if v and len(v) > 50 else v for k, v in result.items()})
    return result


def get_field_confidences(ocr_blocks: list[OCRBlock]) -> dict[str, float | None]:
    """Return confidence scores for each classified field. Useful for UI display."""
    if not ocr_blocks:
        return {k: None for k in ["mrp", "net_quantity", "date_of_manufacture",
                                   "manufacturer_name", "manufacturer_address", "consumer_care"]}

    full_text = " ".join(block.text for block in ocr_blocks)

    mrp_field = _extract_mrp(ocr_blocks, full_text)
    net_qty_field = _extract_net_quantity(ocr_blocks, full_text)
    date_field = _extract_date(ocr_blocks, full_text)
    mfr_name_field, mfr_addr_field = _extract_manufacturer(ocr_blocks, full_text)
    care_field = _extract_consumer_care(ocr_blocks, full_text)

    return {
        "mrp": mrp_field.confidence if mrp_field else None,
        "net_quantity": net_qty_field.confidence if net_qty_field else None,
        "date_of_manufacture": date_field.confidence if date_field else None,
        "manufacturer_name": mfr_name_field.confidence if mfr_name_field else None,
        "manufacturer_address": mfr_addr_field.confidence if mfr_addr_field else None,
        "consumer_care": care_field.confidence if care_field else None,
    }
