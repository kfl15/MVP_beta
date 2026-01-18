# backend/loaders/excel_loader.py
from typing import List
import pandas as pd


def _safe_str(v) -> str:
    if v is None:
        return ""
    # pandas NaN handling
    try:
        if pd.isna(v):
            return ""
    except Exception:
        pass
    s = str(v).strip()
    return s


def extract_text_from_excel(xlsx_path: str, max_rows_per_sheet: int = 5000) -> str:
    """
    Improved for retrieval:
    - Converts each row into a semantic, self-contained line: key=value; key=value; ...
    - Preserves sheet name and row number.
    """
    xls = pd.ExcelFile(xlsx_path)
    parts: List[str] = []

    for sheet in xls.sheet_names:
        df = xls.parse(sheet_name=sheet)

        # Trim huge sheets for MVP stability
        if max_rows_per_sheet and len(df) > max_rows_per_sheet:
            df = df.head(max_rows_per_sheet)

        # Normalize column names
        df.columns = [str(c).strip() for c in df.columns]

        parts.append(f"=== SHEET: {sheet} ===")

        # If empty sheet
        if df.empty:
            parts.append("(empty sheet)")
            continue

        # Semantic rows
        for i, row in df.iterrows():
            kv_pairs = []
            for col in df.columns:
                kv_pairs.append(f"{col}={_safe_str(row.get(col))}")
            # 1-based row number for readability
            parts.append(f"SHEET={sheet} | ROW={i+1}: " + "; ".join(kv_pairs))

    return "\n".join(parts)
