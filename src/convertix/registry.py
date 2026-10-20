import functools
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, features

from .models import Route, Source

WRITER = {"doc", "docx", "odt", "rtf", "txt", "html", "md"}
SHEETS = {"xls", "xlsx", "ods", "csv", "tsv"}
SLIDES = {"ppt", "pptx", "odp"}
IMAGES = {"png", "jpg", "webp", "bmp", "tiff", "gif"}
FILTERS = {"docx": "MS Word 2007 XML", "odt": "writer8", "rtf": "Rich Text Format",
           "txt": "Text (encoded)", "html": "HTML (StarWriter)", "md": "Markdown",
           "xlsx": "Calc MS Excel 2007 XML", "ods": "calc8",
           "csv": "Text - txt - csv (StarCalc)", "tsv": "Text - txt - csv (StarCalc)",
           "pptx": "Impress MS PowerPoint 2007 XML", "odp": "impress8",
           "doc": "MS Word 97", "xls": "MS Excel 97", "ppt": "MS PowerPoint 97"}


@functools.lru_cache(maxsize=1)
def office_filters() -> frozenset[str]:
    """Inspect actual filter registrations, including optional Writer/Calc/Impress modules."""
    if not shutil.which("libreoffice"):
        return frozenset()
    attr = "{http://openoffice.org/2001/registry}name"
    result = set()
    for folder in ("/usr/lib64/libreoffice/share/registry", "/usr/lib/libreoffice/share/registry"):
        for module in ("writer", "calc", "impress"):
            path = Path(folder) / f"{module}.xcd"
            if not path.exists():
                continue
            try:
                for node in ET.parse(path).iter("node"):
                    for prop in node.findall("prop"):
                        if prop.get(attr) == "Flags" and "EXPORT" in (prop.findtext("value") or ""):
                            result.add(node.get(attr, ""))
            except (OSError, ET.ParseError):
                continue
    return frozenset(result)


def routes(source: Source, prefs=None) -> list[Route]:
    import ctypes.util
    if not ctypes.util.find_library("seccomp"):
        return []
    fmt = source.format
    options = []
    filters = office_filters()
    if fmt in WRITER | SHEETS | SLIDES and filters:
        if fmt == "md" and "Markdown" not in filters:
            return []
        targets = (["pdf", "docx", "odt", "rtf", "txt", "html", "md", "doc"] if fmt in WRITER else
                   ["pdf", "xlsx", "ods", "csv", "tsv", "xls"] if fmt in SHEETS else ["pdf", "pptx", "odp", "ppt"])
        family = "writer" if fmt in WRITER else "calc" if fmt in SHEETS else "impress"
        for target in targets:
            filter_name = f"{family}_pdf_Export" if target == "pdf" else FILTERS[target]
            if target == fmt or filter_name not in filters:
                continue
            if target == "pdf" and not shutil.which("pdfinfo"):
                continue
            warning = "La fidelidad depende de LibreOffice y de las fuentes instaladas."
            if target in ("doc", "xls", "ppt"):
                warning = "Formato antiguo de Office: puede perder funciones, diseño o datos que excedan sus límites. Prefiere el formato moderno cuando sea posible."
            elif target in ("csv", "tsv"):
                warning = "Una tabla por hoja, incluidas las ocultas; solo valores, sin fórmulas ni estilos."
            elif target in ("txt", "md"):
                warning = "Puede perder estilos, diseño y objetos que el formato no representa."
            elif target == "html":
                warning = "Los recursos auxiliares se guardan junto al HTML dentro de una carpeta si es necesario."
            elif fmt in ("csv", "tsv"):
                warning = "Texto UTF-8; detecta números simples. No evalúa fórmulas ni infiere fechas."
            options.append(Route(target, "libreoffice", "LibreOffice · conversión local", warning))
    elif fmt in IMAGES:
        Image.init()
        for target in ["png", "jpg", "webp", "pdf", "bmp", "tiff", "gif"]:
            pillow_name = {"jpg": "JPEG", "tiff": "TIFF"}.get(target, target.upper())
            if target == fmt or pillow_name not in Image.SAVE or target == "webp" and not features.check("webp"):
                continue
            if target == "pdf" and not shutil.which("pdfinfo"):
                continue
            # Multiframe input is exported as numbered images or multipage TIFF/PDF.
            warning = ""
            if target in ("jpg", "bmp", "pdf"):
                warning = "La transparencia se compone sobre blanco."
            if target == "gif":
                warning += " GIF reduce la paleta a 256 colores."
            if source.frames > 1:
                if fmt in ("gif", "webp") and target in ("gif", "webp"):
                    warning += " Conserva la animación, duración y bucles. GIF limita colores, alfa y tiempos a centésimas de segundo."
                else:
                    warning += (" Todos los cuadros se guardan como páginas." if target in ("pdf", "tiff") else
                                " Todos los cuadros se guardan como imágenes numeradas; no se conserva el tiempo de animación.")
            options.append(Route(target, "pillow", "Pillow · imágenes locales", warning.strip()))
    elif fmt == "pdf":
        from .config import Preferences
        from .capabilities import pdf_dependencies, ocr_capability
        prefs = prefs or Preferences()
        deps = pdf_dependencies()
        needs_ocr = bool(source.pdf and source.pdf.needs_ocr)
        ocr_ready = deps["pymupdf"] and ocr_capability().supports(prefs.ocr_languages)
        if shutil.which("pdftoppm"):
            for target in ("png", "jpg"):
                options.append(Route(target, "poppler", "Poppler · todas las páginas",
                                     "Todas las páginas como imágenes numeradas; se pierde la selección de texto."))
        if (source.has_text or needs_ocr and ocr_ready) and shutil.which("pdftotext"):
            options.append(Route("txt", "pdf_documents" if needs_ocr and ocr_ready else "poppler", "TXT · texto editable",
                                 "Se utilizará OCR local en las páginas escaneadas." if needs_ocr and ocr_ready else
                                 "Solo texto existente; las páginas escaneadas requieren OCR. Puede cambiar el orden de lectura."))
        if (source.has_text and not needs_ocr or needs_ocr and ocr_ready) and deps["pymupdf"] and deps["docx"]:
            options.append(Route("docx", "pdf_documents", "DOCX · Microsoft Word editable",
                                 ("Se utilizará OCR local; las ilustraciones del escaneo no se separan automáticamente. " if needs_ocr else "")+"Se reconstruyen texto, tablas e imágenes separadas. El diseño puede cambiar."))
        if needs_ocr and ocr_ready:
            options.append(Route("pdf-ocr", "pdf_documents", "PDF con texto seleccionable",
                                 "Añade OCR solo donde falta texto digital; conserva la apariencia y el original."))
        editable = deps["pymupdf"] and (source.has_text and not needs_ocr or needs_ocr and ocr_ready)
        if editable:
            for target, name in (("md", "Markdown"), ("html", "HTML"), ("odt", "OpenDocument"), ("rtf", "Texto enriquecido")):
                if target in ("odt", "rtf") and (not deps["docx"] or FILTERS[target] not in filters):
                    continue
                options.append(Route(target, "pdf_documents", name+" · reconstrucción local",
                                     ("OCR: las ilustraciones del escaneo no se separan automáticamente. " if needs_ocr else "")+"Encabezados, tablas y orden de lectura estimados; el diseño puede cambiar."))
        if editable and deps["openpyxl"] and source.pdf and (source.pdf.tables or source.pdf.scan_tables):
            options.append(Route("xlsx", "pdf_documents", "XLSX · tablas detectadas",
                                 ("Se utilizará OCR. " if needs_ocr else "")+"Una hoja por tabla; se extraen valores. Celdas fusionadas o ambiguas pueden perder estructura."))
        priority = ["docx", "xlsx", "txt", "md", "html", "odt", "rtf", "pdf-ocr", "png", "jpg"]
        options.sort(key=lambda route: priority.index(route.target))
    return options


def common_routes(sources: list[Source], prefs=None) -> list[Route]:
    if not sources:
        return []
    choices = [routes(s, prefs) for s in sources]
    common = set.intersection(*(set(r.target for r in group) for group in choices))
    result = []
    for r in choices[0]:
        if r.target in common:
            warnings = list(dict.fromkeys(x.warning for group in choices for x in group
                                         if x.target == r.target and x.warning))
            result.append(Route(r.target, r.engine, r.description, " ".join(warnings)))
    return result


def diagnostics() -> dict:
    import ctypes.util
    import platform
    from PySide6.QtCore import qVersion
    import PIL
    from .capabilities import pdf_dependencies, ocr_capability
    ocr = ocr_capability()
    return {"python": platform.python_version(), "qt": qVersion(), "pillow": PIL.__version__,
            "tools": {name: shutil.which(name) for name in ("libreoffice", "pdfinfo", "pdftoppm", "pdftotext", "pandoc")},
            "office_filters": sorted(office_filters()), "seccomp": ctypes.util.find_library("seccomp"),
            "pdf_modules": pdf_dependencies(), "ocr": {"executable": ocr.executable, "languages": ocr.languages}}


def extension(target: str) -> str:
    return "pdf" if target == "pdf-ocr" else target

