import os
import tempfile
from functools import lru_cache
from typing import Any, Dict, List

from PIL import Image, ImageEnhance, ImageOps
import pypdfium2 as pdfium


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
PDF_EXTS = {".pdf"}
SUPPORTED_OCR_EXTS = IMAGE_EXTS | PDF_EXTS

OCR_LANG = os.getenv("OCR_LANG", "en")
OCR_PDF_SCALE = float(os.getenv("OCR_PDF_SCALE", "2.5"))
OCR_MIN_WIDTH = int(os.getenv("OCR_MIN_WIDTH", "1400"))
OCR_CONFIDENCE_MIN = float(os.getenv("OCR_CONFIDENCE_MIN", "0.0"))


@lru_cache(maxsize=1)
def _get_ocr():
    from paddleocr import PaddleOCR

    try:
        return PaddleOCR(use_angle_cls=True, lang=OCR_LANG, show_log=False)
    except TypeError:
        return PaddleOCR(use_angle_cls=True, lang=OCR_LANG)


def _prepare_image(image: Image.Image) -> Image.Image:
    image = image.convert("RGB")

    if image.width < OCR_MIN_WIDTH:
        ratio = OCR_MIN_WIDTH / max(1, image.width)
        new_size = (int(image.width * ratio), int(image.height * ratio))
        image = image.resize(new_size, Image.Resampling.LANCZOS)

    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray)
    gray = ImageEnhance.Contrast(gray).enhance(1.6)
    gray = ImageEnhance.Sharpness(gray).enhance(1.4)
    return gray.convert("RGB")


def _parse_paddle_result(result: Any) -> List[Dict[str, Any]]:
    lines: List[Dict[str, Any]] = []

    def walk(node: Any) -> None:
        if not node:
            return

        if (
            isinstance(node, (list, tuple))
            and len(node) >= 2
            and isinstance(node[1], (list, tuple))
            and len(node[1]) >= 2
            and isinstance(node[1][0], str)
        ):
            text = (node[1][0] or "").strip()
            try:
                confidence = float(node[1][1])
            except Exception:
                confidence = None
            if text and (confidence is None or confidence >= OCR_CONFIDENCE_MIN):
                lines.append({"text": text, "confidence": confidence})
            return

        if isinstance(node, (list, tuple)):
            for item in node:
                walk(item)

    walk(result)
    return lines


def _ocr_pil_image(image: Image.Image) -> Dict[str, Any]:
    prepared = _prepare_image(image)

    with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as tmp:
        prepared.save(tmp.name)
        result = _get_ocr().ocr(tmp.name, cls=True)

    lines = _parse_paddle_result(result)
    text = "\n".join(line["text"] for line in lines).strip()
    confidences = [line["confidence"] for line in lines if line["confidence"] is not None]
    avg_confidence = sum(confidences) / len(confidences) if confidences else None

    return {
        "text": text,
        "lines": lines,
        "avg_confidence": avg_confidence,
        "engine": f"paddleocr:{OCR_LANG}",
    }


def extract_ocr_records(file_path: str) -> List[Dict[str, Any]]:
    filename = os.path.basename(file_path)
    ext = os.path.splitext(filename.lower())[1]

    if ext in IMAGE_EXTS:
        with Image.open(file_path) as image:
            ocr = _ocr_pil_image(image)
        return [{
            **ocr,
            "image_name": filename,
            "page_number": None,
            "source_type": "image",
        }]

    if ext in PDF_EXTS:
        records: List[Dict[str, Any]] = []
        pdf = pdfium.PdfDocument(file_path)
        try:
            for page_index in range(len(pdf)):
                page = pdf[page_index]
                bitmap = page.render(scale=OCR_PDF_SCALE)
                image = bitmap.to_pil()
                ocr = _ocr_pil_image(image)
                page_number = page_index + 1
                records.append({
                    **ocr,
                    "image_name": f"{os.path.splitext(filename)[0]}_page_{page_number}.png",
                    "page_number": page_number,
                    "source_type": "pdf_page",
                })
        finally:
            close = getattr(pdf, "close", None)
            if callable(close):
                close()
        return records

    raise ValueError(f"Unsupported OCR file type: {ext}")
