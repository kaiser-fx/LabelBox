"""Field classification service — extracts structured legal-metrology fields from raw OCR blocks.

Takes a list of OCRBlock and returns a dict keyed by field name with extracted values,
matching the interface expected by the Phase 1 rule engine (run_all_rules).
"""

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


# ── MRP ──────────────────────────────────────────────────────────────────────

_MRP_TRIGGER = re.compile(
    r"(M\.?R\.?P\.?|Maximum\s+Retail\s+Price|Retail\s+Price)",
    re.IGNORECASE,
)

# Direct price attached to currency symbol: Rs. 70, Rs 70/-, ₹250, 70 Rs
_CURRENCY_ADJACENT_PRICE = re.compile(
    r"(?:₹|Rs\.?|INR)\s*[:\-]?\s*(\d+(?:[.,]\d{1,2})?(?:\s*/\s*[-=])?)",
    re.IGNORECASE,
)

# MRP followed directly by a clean number: MRP 250, M.R.P.: 150.00 (not a fraction like 0/5)
_MRP_CLEAN_PRICE = re.compile(
    r"\b(?:MRP|M\.?R\.?P\.?|Maximum\s+Retail\s+Price|Max\s*\.?\s*Retail\s*\.?\s*Price)\s*[:\-]?\s*(\d+(?:[.,]\d{1,2})?)(?!\s*/\s*[0-9a-zA-Z])(?:\s*/\s*[-=])?",
    re.IGNORECASE,
)

# Price in an adjacent or standalone block: '70 / -', '70/-', '75 / -', 'Rs. 70', '₹150.00'
_ADJACENT_PRICE = re.compile(
    r"^\s*(?:₹|Rs\.?|INR)?\s*[:\-]?\s*(\d+(?:[.,]\d{1,2})?(?:\s*/\s*[-=])?)",
    re.IGNORECASE,
)

# Broader catch for currency symbol near a number when no explicit "MRP" keyword
_CURRENCY_STANDALONE = re.compile(
    r"(?:₹|Rs\.?)\s*(\d+(?:[.,]\d{1,2})?(?:\s*/\s*[-=])?)",
    re.IGNORECASE,
)

_INCL_TAXES = re.compile(r"\(?\s*incl(?:usive)?\b.*tax", re.IGNORECASE)


def _has_inline_price(text: str) -> bool:
    """Check if a block with an MRP trigger actually contains the price value itself."""
    # If currency symbol exists: price MUST be attached to the currency symbol
    if re.search(r"(?:₹|Rs\.?|INR)\b", text, re.IGNORECASE):
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
    # Strategy 1: Find block(s) with MRP keyword that ALREADY contain the complete price
    for block in blocks:
        if _MRP_TRIGGER.search(block.text):
            if _has_inline_price(block.text):
                return ClassifiedField(
                    field_name="mrp",
                    value=block.text.strip(),
                    confidence=block.confidence,
                    source_texts=[block.text],
                )

    # Strategy 2: MRP keyword in one block, price in the next adjacent block (within 2 blocks)
    for i, block in enumerate(blocks):
        if _MRP_TRIGGER.search(block.text):
            # Check adjacent block for price
            if i + 1 < len(blocks):
                next_block = blocks[i + 1]
                if _ADJACENT_PRICE.search(next_block.text):
                    combined = f"{block.text.strip()} {next_block.text.strip()}"
                    source_texts = [block.text, next_block.text]
                    avg_conf = (block.confidence + next_block.confidence) / 2

                    # Check if following block contains tax declaration
                    if i + 2 < len(blocks) and _INCL_TAXES.search(blocks[i + 2].text):
                        combined = f"{combined} {blocks[i + 2].text.strip()}"
                        source_texts.append(blocks[i + 2].text)

                    return ClassifiedField(
                        field_name="mrp",
                        value=combined,
                        confidence=avg_conf,
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
                value=snippet,
                confidence=0.7,
                source_texts=[snippet],
            )

    # Strategy 4: Fallback to standalone currency symbol with price (even without explicit 'MRP')
    for block in blocks:
        match = _CURRENCY_STANDALONE.search(block.text)
        if match:
            return ClassifiedField(
                field_name="mrp",
                value=block.text.strip(),
                confidence=block.confidence * 0.8,
                source_texts=[block.text],
            )

    return None


# ── Net Quantity ─────────────────────────────────────────────────────────────

_NET_QTY_TRIGGER = re.compile(
    r"(Net\s*\.?\s*(Qty|Quantity|Wt|Weight|Content|Volume|Cont)"
    r"|Net\s+\d"  # "Net 200g" without explicit keyword
    r"|Contents?\s*:)",
    re.IGNORECASE,
)

_QTY_VALUE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(g|gm|gms|gram|grams|kg|kilogram|kilograms"
    r"|ml|millilitre|millilitres|milliliter|milliliters"
    r"|l|litre|litres|liter|liters"
    r"|cm|m|mm|pieces|pcs|nos|units)\b",
    re.IGNORECASE,
)


def _extract_net_quantity(blocks: list[OCRBlock], full_text: str) -> ClassifiedField | None:
    """Look for net quantity declaration."""
    # Strategy 1: block with trigger keyword + quantity value
    for block in blocks:
        if _NET_QTY_TRIGGER.search(block.text):
            qty_match = _QTY_VALUE.search(block.text)
            if qty_match:
                return ClassifiedField(
                    field_name="net_quantity",
                    value=block.text.strip(),
                    confidence=block.confidence,
                    source_texts=[block.text],
                )

    # Strategy 2: trigger in one block, value in the next
    for i, block in enumerate(blocks):
        if _NET_QTY_TRIGGER.search(block.text):
            if i + 1 < len(blocks):
                next_block = blocks[i + 1]
                qty_match = _QTY_VALUE.search(next_block.text)
                if qty_match:
                    combined = f"{block.text.strip()} {next_block.text.strip()}"
                    avg_conf = (block.confidence + next_block.confidence) / 2
                    return ClassifiedField(
                        field_name="net_quantity",
                        value=combined,
                        confidence=avg_conf,
                        source_texts=[block.text, next_block.text],
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
                value=snippet,
                confidence=0.7,
                source_texts=[snippet],
            )

    return None


# ── Date of Manufacture ──────────────────────────────────────────────────────

_DATE_TRIGGER = re.compile(
    r"(Mf[gd]\.?\s*(?:Date|Dt)?|Manufacture[ds]?\s*(?:Date|On)?"
    r"|Pk[dt]\.?\s*(?:Date|Dt)?|Pack(?:ed|ing)\s*(?:Date|On)?"
    r"|Best\s+Before|Exp(?:iry)?\s*(?:Date|Dt)?"
    r"|Use\s+Before|BB\s*:|Date\s+of\s+Mfg)",
    re.IGNORECASE,
)

# Reuse the same date patterns from Phase 1 rule engine
_DATE_PATTERNS = [
    re.compile(r"\b(0[1-9]|1[0-2])[/\-](19|20)\d{2}\b"),
    re.compile(r"\b(0[1-9]|[12]\d|3[01])[/\-](0[1-9]|1[0-2])[/\-](19|20)\d{2}\b"),
    re.compile(
        r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
        r"Dec(?:ember)?)\s*'?\s*(19|20)\d{2}\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(19|20)\d{2}[/\-](0[1-9]|1[0-2])[/\-](0[1-9]|[12]\d|3[01])\b"),
]


def _extract_date(blocks: list[OCRBlock], full_text: str) -> ClassifiedField | None:
    """Look for manufacture/packing date declaration."""
    # Strategy 1: block with date trigger + parseable date
    for block in blocks:
        if _DATE_TRIGGER.search(block.text):
            for pattern in _DATE_PATTERNS:
                if pattern.search(block.text):
                    return ClassifiedField(
                        field_name="date_of_manufacture",
                        value=block.text.strip(),
                        confidence=block.confidence,
                        source_texts=[block.text],
                    )

    # Strategy 2: trigger in one block, date in the next
    for i, block in enumerate(blocks):
        if _DATE_TRIGGER.search(block.text):
            # Maybe the date is embedded in the same block without matching patterns
            for pattern in _DATE_PATTERNS:
                if pattern.search(block.text):
                    return ClassifiedField(
                        field_name="date_of_manufacture",
                        value=block.text.strip(),
                        confidence=block.confidence,
                        source_texts=[block.text],
                    )
            # Check next block
            if i + 1 < len(blocks):
                next_block = blocks[i + 1]
                for pattern in _DATE_PATTERNS:
                    if pattern.search(next_block.text):
                        combined = f"{block.text.strip()} {next_block.text.strip()}"
                        avg_conf = (block.confidence + next_block.confidence) / 2
                        return ClassifiedField(
                            field_name="date_of_manufacture",
                            value=combined,
                            confidence=avg_conf,
                            source_texts=[block.text, next_block.text],
                        )

    # Strategy 3: full text fallback — find trigger near a date
    trigger_match = _DATE_TRIGGER.search(full_text)
    if trigger_match:
        # Look for a date within 40 chars after the trigger
        window = full_text[trigger_match.start():trigger_match.start() + 60]
        for pattern in _DATE_PATTERNS:
            if pattern.search(window):
                return ClassifiedField(
                    field_name="date_of_manufacture",
                    value=window.strip(),
                    confidence=0.7,
                    source_texts=[window.strip()],
                )

    # Strategy 4: any date anywhere (low confidence, no trigger keyword found)
    for block in blocks:
        for pattern in _DATE_PATTERNS:
            if pattern.search(block.text):
                return ClassifiedField(
                    field_name="date_of_manufacture",
                    value=block.text.strip(),
                    confidence=block.confidence * 0.5,  # halved — no trigger keyword
                    source_texts=[block.text],
                )

    return None


# ── Manufacturer Name & Address ──────────────────────────────────────────────

_MFR_TRIGGER = re.compile(
    r"(Mf[gd]\.?\s*(?:by|By)|Manufactured\s+by|Marketed\s+by"
    r"|Pk[dt]\.?\s*(?:by|By)|Packed\s+by|Packer\s*:"
    r"|Importer\s*:|Imported\s+by)",
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
        if trigger_match:
            # Text after the trigger keyword in this block is the start of the name
            after_trigger = block.text[trigger_match.end():].strip()
            # Remove leading punctuation/colon
            after_trigger = re.sub(r"^[\s:,\-]+", "", after_trigger)

            collected_parts = []
            if after_trigger:
                collected_parts.append(after_trigger)

            confidences = [block.confidence]

            # Gather subsequent blocks until we hit another section keyword or run out
            for j in range(i + 1, min(i + 5, len(blocks))):
                next_block = blocks[j]
                # Stop if we hit a different section trigger
                if (_MRP_TRIGGER.search(next_block.text)
                        or _NET_QTY_TRIGGER.search(next_block.text)
                        or _DATE_TRIGGER.search(next_block.text)
                        or re.search(r"(Consumer|Customer|Helpline|Toll Free)", next_block.text, re.IGNORECASE)):
                    break
                collected_parts.append(next_block.text.strip())
                confidences.append(next_block.confidence)

            if not collected_parts:
                continue

            full_mfr_text = ", ".join(collected_parts)
            avg_conf = sum(confidences) / len(confidences)

            # Try to split into name vs address
            # Heuristic: first part is name, rest (especially if containing a PIN code) is address
            name_part = collected_parts[0]
            address_parts = collected_parts[1:] if len(collected_parts) > 1 else []

            # If the first part itself contains a comma, split at first comma
            if "," in name_part and not address_parts:
                split_idx = name_part.index(",")
                address_parts = [name_part[split_idx + 1:].strip()]
                name_part = name_part[:split_idx].strip()

            name_field = ClassifiedField(
                field_name="manufacturer_name",
                value=name_part,
                confidence=avg_conf,
                source_texts=collected_parts[:1],
            )

            address_text = ", ".join(address_parts) if address_parts else ""
            address_field = None
            if address_text:
                address_field = ClassifiedField(
                    field_name="manufacturer_address",
                    value=address_text,
                    confidence=avg_conf,
                    source_texts=address_parts,
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
    r"(Consumer|Customer\s*Care|Helpline|Toll\s*Free|Contact\s*Us"
    r"|Customer\s*Service|Grievance|Complaint)",
    re.IGNORECASE,
)

_PHONE_PATTERN = re.compile(
    r"(?:\+91[\s\-]?)?(?:\d[\s\-]?){10}"
    r"|1800[\s\-]?\d{3}[\s\-]?\d{3,5}"
    r"|\d{3,5}[\s\-]?\d{6,8}",
)

_EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


def _extract_consumer_care(blocks: list[OCRBlock], full_text: str) -> ClassifiedField | None:
    """Look for consumer care contact details (phone or email)."""
    # Strategy 1: block with trigger + phone/email
    for block in blocks:
        if _CARE_TRIGGER.search(block.text):
            has_phone = _PHONE_PATTERN.search(block.text)
            has_email = _EMAIL_PATTERN.search(block.text)
            if has_phone or has_email:
                return ClassifiedField(
                    field_name="consumer_care",
                    value=block.text.strip(),
                    confidence=block.confidence,
                    source_texts=[block.text],
                )

    # Strategy 2: trigger in one block, contact in next
    for i, block in enumerate(blocks):
        if _CARE_TRIGGER.search(block.text):
            # Collect this block and up to 2 subsequent blocks
            collected = [block.text.strip()]
            confidences = [block.confidence]
            for j in range(i + 1, min(i + 3, len(blocks))):
                collected.append(blocks[j].text.strip())
                confidences.append(blocks[j].confidence)

            combined = " ".join(collected)
            has_phone = _PHONE_PATTERN.search(combined)
            has_email = _EMAIL_PATTERN.search(combined)
            if has_phone or has_email:
                return ClassifiedField(
                    field_name="consumer_care",
                    value=combined,
                    confidence=sum(confidences) / len(confidences),
                    source_texts=collected,
                )

    # Strategy 3: full text
    trigger_match = _CARE_TRIGGER.search(full_text)
    if trigger_match:
        window = full_text[trigger_match.start():trigger_match.start() + 120]
        has_phone = _PHONE_PATTERN.search(window)
        has_email = _EMAIL_PATTERN.search(window)
        if has_phone or has_email:
            return ClassifiedField(
                field_name="consumer_care",
                value=window.strip(),
                confidence=0.7,
                source_texts=[window.strip()],
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
