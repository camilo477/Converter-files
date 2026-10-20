"""Selective local Tesseract OCR. Original page graphics are kept; only hidden text is added."""
import csv
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from ..capabilities import ocr_capability
from ..config import Preferences
from ..models import ConversionError, Source
from ..process import run


def searchable(source: Source, destination: Path, prefs: Preferences) -> Path:
    import pymupdf
    profile = source.pdf
    if not profile or not profile.needs_ocr:
        return source.path
    capability = ocr_capability()
    if not capability.supports(prefs.ocr_languages):
        missing = set(prefs.ocr_languages.split("+"))-set(capability.languages)
        raise ConversionError("OCR no disponible. Falta Tesseract o los idiomas: " + ", ".join(sorted(missing)))
    workspace = destination.parent/"ocr-work"
    workspace.mkdir(mode=0o700)
    with pymupdf.open(source.path) as document:
        for index, page_info in enumerate(profile.pages):
            if not page_info.needs_ocr:
                continue
            (destination.parent/"progress.txt").write_text(f"OCR página {index+1}/{len(document)} · {prefs.ocr_languages}")
            page = document[index]
            rotation = page.rotation
            page.set_rotation(0)
            if page.rect.width*page.rect.height*(300/72)**2 > 150_000_000:
                raise ConversionError("La página es demasiado grande para OCR a 300 ppp.")
            pix = page.get_pixmap(dpi=300, colorspace=pymupdf.csGRAY, alpha=False)
            image = ImageOps.autocontrast(Image.frombytes("L", (pix.width, pix.height), pix.samples))
            # Mask existing digital text in the OCR input, preserving it in the original PDF.
            draw = ImageDraw.Draw(image)
            for trace in page.get_texttrace():
                if trace["type"] != 3 and trace.get("opacity", 1) > 0.1:
                    box = pymupdf.Rect(trace["bbox"])*pymupdf.Matrix(300/72, 300/72)
                    draw.rectangle((box.x0-2,box.y0-2,box.x1+2,box.y1+2), fill=255)
            input_image = workspace/f"page-{index+1:04}.png"
            prefix = workspace/f"page-{index+1:04}"
            image.save(input_image, dpi=(300,300))
            env = os.environ.copy(); env["OMP_THREAD_LIMIT"] = "1"
            run([capability.executable, str(input_image), str(prefix), "-l", prefs.ocr_languages,
                 "--dpi", "300", "--psm", "3", "-c", "textonly_pdf=1", "pdf", "tsv"],
                timeout=prefs.timeout, env=env)
            with prefix.with_suffix(".tsv").open(encoding="utf-8") as f:
                words = [r for r in csv.DictReader(f, delimiter="\t") if r.get("text", "").strip() and float(r["conf"]) >= 0]
            confidence = sum(float(w["conf"])*len(w["text"]) for w in words)/max(1,sum(len(w["text"]) for w in words))
            if sum(len(w["text"].strip()) for w in words) < 3 or confidence < 25:
                raise ConversionError(f"OCR sin texto utilizable o de confianza demasiado baja en la página {index+1}. No se publicó un resultado parcial.")
            with pymupdf.open(prefix.with_suffix(".pdf")) as layer:
                if not layer[0].get_text().strip():
                    raise ConversionError(f"La capa OCR de la página {index+1} está vacía.")
                page.show_pdf_page(page.rect, layer, 0, overlay=True)
            page.set_rotation(rotation)
            input_image.unlink()
        document.save(destination, garbage=3, deflate=True)
    with pymupdf.open(destination) as check:
        if len(check) != len(profile.pages):
            raise ConversionError("El PDF OCR no conserva todas las páginas.")
        for i, info in enumerate(profile.pages):
            if info.needs_ocr and not check[i].get_text().strip():
                raise ConversionError("Falta texto en una página que requería OCR.")
    return destination
