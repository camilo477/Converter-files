"""MuPDF document reconstruction, with explicitly validated intermediate files."""
from pathlib import Path

from ..config import Preferences
from ..models import ConversionError, Source
from ..pdf_layout import extract_page
from ..pdf_export import to_docx, to_xlsx, markdown, html_document


def report(output: Path, text: str) -> None:
    (output.parent/"progress.txt").write_text(text)


def convert(source: Source, target: str, output: Path, prefs: Preferences) -> None:
    import pymupdf
    from .ocr import searchable
    normalized = searchable(source, output.parent/"ocr.pdf", prefs)
    if target == "pdf-ocr":
        if normalized == source.path:
            raise ConversionError("El PDF ya contiene texto o no necesita OCR.")
        import shutil
        shutil.copyfile(normalized, output/"document.pdf")
        return
    if target == "txt":
        from ..process import run
        destination = output/"document.txt"
        run(["pdftotext", "-layout", "-enc", "UTF-8", str(normalized), str(destination)], timeout=prefs.timeout)
        if not destination.read_text().strip():
            raise ConversionError("No se obtuvo texto extraíble ni mediante OCR.")
        return
    with pymupdf.open(normalized) as document:
        pages = []
        for page in document:
            report(output, f"Reconstruyendo página {page.number+1}/{len(document)}…")
            page.remove_rotation()
            page_info = source.pdf.pages[page.number] if source.pdf else None
            pages.append(extract_page(page, from_scan=bool(page_info and page_info.kind in ("scanned", "mixed", "ocr"))))
        if target == "docx":
            to_docx(pages, output/"document.docx")
        elif target == "xlsx":
            to_xlsx(pages, output/"document.xlsx")
        elif target == "md":
            markdown(pages, output)
        elif target == "html":
            html_document(pages, output)
        elif target in ("odt", "rtf"):
            bridge = output.parent/"bridge.docx"
            to_docx(pages, bridge)
            from ..detect import zip_format
            if zip_format(bridge) != "docx":
                raise ConversionError("Falló la validación del DOCX intermedio.")
            from .office import convert as office_convert
            office_convert(Source(bridge, "docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"), target, output, prefs)
        else:
            raise ConversionError("Destino PDF editable no implementado.")
