from pypdf import PdfReader


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract full text from a PDF file.
    """
    reader = PdfReader(pdf_path)
    text_parts = []

    for page_number, page in enumerate(reader.pages):
        page_text = page.extract_text()
        if page_text:
            text_parts.append(page_text)

    return "\n".join(text_parts)


if __name__ == "__main__":
    # Simple local test
    import sys
    if len(sys.argv) != 2:
        print("Usage: python pdf_loader.py <pdf_path>")
        sys.exit(1)

    print(extract_text_from_pdf(sys.argv[1])[:1000])
