"""
Export Generator — CSV and Excel export for batch results.
"""
import io
import logging
from typing import List, Dict, Any

import pandas as pd

logger = logging.getLogger(__name__)


def _build_row(doc_data: Dict[str, Any], approval_mode: str = "auto") -> Dict[str, Any]:
    """Flatten a document result dict into exactly the requested columns."""
    candidate = doc_data.get("candidate", {}) or {}
    extraction = doc_data.get("extraction_result", {}) or {}
    eligibility = doc_data.get("eligibility_result", {}) or {}

    overall_pct = extraction.get("overall_percentage")
    pct_str = f"{overall_pct:.2f}%" if overall_pct is not None else ""

    # Resolve status based on approval mode
    status = eligibility.get("status", "") or doc_data.get("status", "") or "REVIEW_REQUIRED"
    
    if eligibility.get("is_manually_reviewed") or eligibility.get("override_status"):
        resolved_status = eligibility.get("override_status") or status
    elif approval_mode == "auto" and status == "REVIEW_REQUIRED":
        threshold = eligibility.get("eligibility_threshold", 50.0)
        if overall_pct is not None:
            resolved_status = "ELIGIBLE" if overall_pct > threshold else "NOT_ELIGIBLE"
        else:
            resolved_status = "NOT_ELIGIBLE"
    else:
        resolved_status = status

    return {
        "Student's Name": candidate.get("name", "") or "Unknown",
        "Application Number": candidate.get("register_number", "") or "N/A",
        "Percentage": pct_str,
        "Eligibility Status": resolved_status,
    }


def _fmt(val) -> str:
    if val is None:
        return ""
    if isinstance(val, float):
        return f"{val:.2f}"
    return str(val)


def generate_csv(rows: List[Dict[str, Any]], approval_mode: str = "auto") -> bytes:
    """Generate a CSV export from a list of document result dicts."""
    flat_rows = [_build_row(r, approval_mode) for r in rows]
    df = pd.DataFrame(flat_rows)
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


def generate_excel(rows: List[Dict[str, Any]], approval_mode: str = "auto") -> bytes:
    """Generate an Excel (.xlsx) export from document result dicts."""
    flat_rows = [_build_row(r, approval_mode) for r in rows]
    df = pd.DataFrame(flat_rows)

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Results")

        # Auto-size columns
        worksheet = writer.sheets["Results"]
        for col in worksheet.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            worksheet.column_dimensions[col[0].column_letter].width = min(max_len + 4, 50)

        # Freeze header row
        worksheet.freeze_panes = "A2"

        # Color-code eligibility column
        from openpyxl.styles import PatternFill
        green_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
        red_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
        orange_fill = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")

        status_col_idx = list(df.columns).index("Eligibility Status") + 1
        for row_idx, row_data in enumerate(flat_rows, start=2):
            cell = worksheet.cell(row=row_idx, column=status_col_idx)
            val = row_data.get("Eligibility Status")
            if val == "ELIGIBLE":
                cell.fill = green_fill
            elif val == "NOT_ELIGIBLE":
                cell.fill = red_fill
            elif val == "REVIEW_REQUIRED":
                cell.fill = orange_fill

    buf.seek(0)
    return buf.getvalue()
