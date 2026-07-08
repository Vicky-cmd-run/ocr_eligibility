"""
Layout Analyzer — uses bounding-box spatial relationships to
associate subject name tokens with marks columns.
Works on a list of OcrToken objects from a single page.
"""
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict

from app.core.ocr_engine import OcrToken

logger = logging.getLogger(__name__)

# How much vertical overlap (in pixels/units) tokens need to be "on the same row"
ROW_Y_TOLERANCE = 35.0

# Patterns for detecting numeric mark values
NUMERIC_PATTERN = re.compile(r"^\d{1,3}(\.\d{1,2})?$")
ABSENT_PATTERN = re.compile(r"^(ab|abs|absent|--|-|na|n/?a)$", re.IGNORECASE)
GRADE_PATTERN = re.compile(r"^[a-dA-D][+\-]?$")


@dataclass
class TableRow:
    """A single detected row in the marks table."""
    subject_token: OcrToken
    mark_tokens: List[OcrToken] = field(default_factory=list)
    # Best candidates for obtained/max marks
    obtained_text: Optional[str] = None
    maximum_text: Optional[str] = None
    obtained_confidence: float = 0.0
    maximum_confidence: float = 0.0
    row_y_center: float = 0.0


def tokens_on_same_row(t1: OcrToken, t2: OcrToken, tolerance: float = ROW_Y_TOLERANCE) -> bool:
    """True if two tokens share approximately the same vertical center."""
    c1 = (t1.y_min + t1.y_max) / 2
    c2 = (t2.y_min + t2.y_max) / 2
    
    # Dynamically scale tolerance based on token heights for cross-resolution consistency
    h1 = t1.y_max - t1.y_min
    h2 = t2.y_max - t2.y_min
    avg_h = (h1 + h2) / 2
    
    # 45% of the average text height is standard for same-line deviation
    dynamic_tol = max(avg_h * 0.45, 12.0)
    return abs(c1 - c2) <= dynamic_tol


def is_numeric_or_absent(text: str) -> bool:
    """True if text looks like a mark value (number) or an absence marker."""
    t = text.strip()
    return bool(NUMERIC_PATTERN.match(t)) or bool(ABSENT_PATTERN.match(t))


def clean_numeric(text: str) -> Optional[float]:
    """Parse a numeric mark string into a float. Returns None on failure."""
    t = text.strip().replace(",", ".")
    if ABSENT_PATTERN.match(t):
        return None
    try:
        return float(t)
    except ValueError:
        return None


def detect_column_x_positions(tokens: List[OcrToken]) -> List[float]:
    """
    Cluster numeric tokens by x-position to detect column boundaries.
    Returns sorted list of cluster center x values.
    """
    numeric_tokens = [t for t in tokens if is_numeric_or_absent(t.text)]
    if not numeric_tokens:
        return []

    # Simple 1D clustering by x_min center
    centers = [(t.x_min + t.x_max) / 2 for t in numeric_tokens]
    clusters: List[List[float]] = []

    for c in sorted(centers):
        placed = False
        for cluster in clusters:
            if abs(c - cluster[-1]) < 40:  # merge if within 40 units
                cluster.append(c)
                placed = True
                break
        if not placed:
            clusters.append([c])

    return sorted(sum(c) / len(c) for c in clusters)


def group_tokens_into_rows(tokens: List[OcrToken]) -> List[List[OcrToken]]:
    """
    Group tokens into rows based on vertical proximity.
    Returns list of rows; each row is a list of tokens sorted left→right.
    """
    if not tokens:
        return []

    sorted_tokens = sorted(tokens, key=lambda t: t.y_min)
    rows: List[List[OcrToken]] = []
    current_row = [sorted_tokens[0]]

    for token in sorted_tokens[1:]:
        if tokens_on_same_row(current_row[-1], token):
            current_row.append(token)
        else:
            rows.append(sorted(current_row, key=lambda t: t.x_min))
            current_row = [token]

    if current_row:
        rows.append(sorted(current_row, key=lambda t: t.x_min))

    return rows


def identify_header_row(rows: List[List[OcrToken]]) -> Optional[int]:
    """
    Find the index of the table header row (containing words like 'obtained', 'maximum', 'marks').
    Returns row index or None.
    """
    header_keywords = {"obtained", "maximum", "max", "marks", "score", "theory", "practical", "total"}
    for i, row in enumerate(rows):
        row_text = " ".join(t.text.lower() for t in row)
        matches = sum(1 for kw in header_keywords if kw in row_text)
        if matches >= 2:
            return i
    return None


def infer_column_roles(header_row: List[OcrToken]) -> Dict[str, Optional[float]]:
    """
    From a header row, determine which x-range corresponds to
    'obtained' and 'maximum' columns.
    Returns dict with 'obtained_x' and 'maximum_x' (x-centers).
    """
    roles: Dict[str, Optional[float]] = {"obtained_x": None, "maximum_x": None}
    for token in header_row:
        text = token.text.lower()
        x_center = (token.x_min + token.x_max) / 2
        if any(kw in text for kw in ("obtained", "marks", "scored", "got")):
            roles["obtained_x"] = x_center
        elif any(kw in text for kw in ("max", "maximum", "total", "out of")):
            roles["maximum_x"] = x_center
    return roles


def extract_table_rows(tokens: List[OcrToken]) -> List[TableRow]:
    """
    Main layout analysis function.
    Groups tokens into rows, identifies subject column vs mark columns,
    returns TableRow list with subject + obtained/max mark associations.
    """
    rows = group_tokens_into_rows(tokens)
    if not rows:
        return []

    # Try to find header row
    header_idx = identify_header_row(rows)
    column_roles: Dict[str, Optional[float]] = {"obtained_x": None, "maximum_x": None}
    if header_idx is not None and header_idx < len(rows):
        column_roles = infer_column_roles(rows[header_idx])

    # Detect column x-positions from all numeric tokens
    all_numeric_tokens = [t for row in rows for t in row if is_numeric_or_absent(t.text)]
    col_xs = detect_column_x_positions(tokens)

    table_rows: List[TableRow] = []
    start_idx = (header_idx + 1) if header_idx is not None else 0

    for row in rows[start_idx:]:
        if not row:
            continue

        # Separate text tokens (likely subject names) and numeric tokens
        text_tokens = [t for t in row if not is_numeric_or_absent(t.text) and len(t.text) >= 2]
        num_tokens = [t for t in row if is_numeric_or_absent(t.text)]

        if not text_tokens or len(text_tokens[0].text) < 2:
            continue

        # First text token on the left is most likely the subject name
        subject_token = min(text_tokens, key=lambda t: t.x_min)

        if not num_tokens:
            continue

        table_row = TableRow(
            subject_token=subject_token,
            mark_tokens=num_tokens,
            row_y_center=(subject_token.y_min + subject_token.y_max) / 2,
        )

        # Assign obtained / maximum using column roles or positional heuristics
        _assign_obtained_maximum(table_row, column_roles, col_xs)
        table_rows.append(table_row)

    return table_rows


def _assign_obtained_maximum(
    row: TableRow,
    column_roles: Dict[str, Optional[float]],
    col_xs: List[float],
) -> None:
    """
    Assign obtained and maximum marks from numeric tokens in the row.
    Filters out subject codes and identifies splits totals with 100 marks fallback.
    """
    # 1. Filter out subject codes (numeric tokens to the left of the subject name)
    subj_x = row.subject_token.x_min
    num_tokens = [t for t in row.mark_tokens if t.x_min > subj_x]
    num_tokens = sorted(num_tokens, key=lambda t: t.x_min)
    
    if not num_tokens:
        return
        
    vals = []
    for t in num_tokens:
        val = clean_numeric(t.text)
        if val is not None:
            vals.append((val, t))
            
    if not vals:
        return

    # If we only have 1 numeric token, it is obtained marks, max is 100
    if len(vals) == 1:
        row.obtained_text = vals[0][1].text
        row.obtained_confidence = vals[0][1].confidence
        row.maximum_text = "100"
        row.maximum_confidence = 1.0
        return

    # If we have 3 numeric tokens: check if 3rd is the sum of 1st and 2nd (Theory + Practical = Total)
    if len(vals) == 3:
        v1, t1 = vals[0]
        v2, t2 = vals[1]
        v3, t3 = vals[2]
        if abs((v1 + v2) - v3) <= 2:
            row.obtained_text = t3.text
            row.obtained_confidence = t3.confidence
            row.maximum_text = "100"
            row.maximum_confidence = 1.0
            return

    # If we have 2 numeric tokens (e.g., Obtained and Maximum, or Split and Total)
    if len(vals) == 2:
        v1, t1 = vals[0]
        v2, t2 = vals[1]
        
        # If the second value is a common max mark or larger than first
        if v2 in (100, 50, 200, 150, 75, 80, 90) or v2 > v1:
            row.obtained_text = t1.text
            row.obtained_confidence = t1.confidence
            row.maximum_text = t2.text
            row.maximum_confidence = t2.confidence
        else:
            row.obtained_text = t2.text
            row.obtained_confidence = t2.confidence
            row.maximum_text = "100"
            row.maximum_confidence = 1.0
        return

    # Fallback default: pick the largest value as obtained, max is 100
    max_val, max_token = max(vals, key=lambda x: x[0])
    row.obtained_text = max_token.text
    row.obtained_confidence = max_token.confidence
    row.maximum_text = "100"
    row.maximum_confidence = 1.0
