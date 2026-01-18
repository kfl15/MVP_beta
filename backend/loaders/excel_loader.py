# backend/loaders/excel_loader.py
from typing import List
import pandas as pd

def extract_text_from_excel(xlsx_path: str, max_rows_per_sheet: int = 5000) -> str:
    """
    Simple MVP: read each sheet, convert rows to a readable text block.
    """
    xls = pd.ExcelFile(xlsx_path)
    parts: List[str] = []

    for sheet in xls.sheet_names:
        df = xls.parse(sheet_name=sheet)

        # trim huge sheets for MVP stability (adjust later)
        if max_rows_per_sheet and len(df) > max_rows_per_sheet:
            df = df.head(max_rows_per_sheet)

        parts.append(f"=== SHEET: {sheet} ===")
        # Convert to text; keep headers + rows
        parts.append(df.to_csv(index=False))

    return "\n".join(parts)
