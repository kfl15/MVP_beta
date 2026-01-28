# backend/loaders/excel_loader.py
from __future__ import annotations
from typing import List, Dict, Any, Optional
import pandas as pd


def _safe_str(v) -> str:
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except Exception:
        pass
    return str(v).strip()


def extract_excel_chunks(
    xlsx_path: str,
    rows_per_chunk: int = 100,
    max_rows_per_sheet: int = 0,  # 0 = no cap
) -> List[Dict[str, Any]]:
    """
    Production-friendly Excel chunking:
    - Converts each row into a semantic line: col=value; col=value; ...
    - Groups rows into row-block chunks (rows_per_chunk) to preserve row boundaries.
    - Adds metadata: sheet_name, row_start, row_end.
    - Avoids silent truncation unless max_rows_per_sheet > 0.
    """
    xls = pd.ExcelFile(xlsx_path)
    out: List[Dict[str, Any]] = []

    for sheet in xls.sheet_names:
        df = xls.parse(sheet_name=sheet)

        if max_rows_per_sheet and len(df) > max_rows_per_sheet:
            df = df.head(max_rows_per_sheet)

        if df is None or df.empty:
            out.append({
                "text": f"=== SHEET: {sheet} ===\n(empty sheet)",
                "meta": {"sheet_name": sheet, "row_start": None, "row_end": None},
            })
            continue

        df.columns = [str(c).strip() for c in df.columns]

        # Build row-lines first (1-based row numbers)
        row_lines: List[str] = []
        for i, row in df.iterrows():
            kv = [f"{col}={_safe_str(row.get(col))}" for col in df.columns]
            row_lines.append(f"ROW={i+1}: " + "; ".join(kv))

        # Group into row blocks
        n = len(row_lines)
        if rows_per_chunk <= 0:
            rows_per_chunk = 100

        start = 0
        while start < n:
            end = min(start + rows_per_chunk, n)
            row_start = start + 1
            row_end = end

            header = f"=== SHEET: {sheet} | ROWS {row_start}-{row_end} ==="
            body = "\n".join(row_lines[start:end])

            out.append({
                "text": header + "\n" + body,
                "meta": {"sheet_name": sheet, "row_start": row_start, "row_end": row_end},
            })

            start = end

    return out


# Backward compatibility (if anything still calls it)
def extract_text_from_excel(xlsx_path: str, max_rows_per_sheet: int = 5000) -> str:
    chunks = extract_excel_chunks(
        xlsx_path=xlsx_path,
        rows_per_chunk=200,  # reasonable default
        max_rows_per_sheet=max_rows_per_sheet,
    )
    return "\n\n".join(c["text"] for c in chunks)
