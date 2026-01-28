from __future__ import annotations
from typing import List, Tuple
from pypdf import PdfReader


def extract_pages_from_pdf(pdf_path: str) -> List[Tuple[int, str]]:
    """
    Returns (page_number_1based, text) for each page.
    """
    reader = PdfReader(pdf_path)
    pages: List[Tuple[int, str]] = []

    for i, page in enumerate(reader.pages):
        t = page.extract_text() or ""
        t = t.strip()
        if t:
            pages.append((i + 1, t))

    return pages


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Backward compatibility: full text join.
    """
    pages = extract_pages_from_pdf(pdf_path)
    return "\n".join(t for _, t in pages)
