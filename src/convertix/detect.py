"""Content-first detection with bounded structural validation."""
import csv
import codecs
import io
import os
import re
import stat
import warnings
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from PySide6.QtCore import QMimeDatabase
from PIL import Image, UnidentifiedImageError

from .models import ConversionError, Source
from .process import run

IMAGE_FORMATS = {"PNG": "png", "JPEG": "jpg", "WEBP": "webp", "BMP": "bmp", "TIFF": "tiff", "GIF": "gif"}
ZIP_FORMATS = {"word/document.xml": "docx", "xl/workbook.xml": "xlsx", "ppt/presentation.xml": "pptx"}
ODF = {"application/vnd.oasis.opendocument.text": "odt",
       "application/vnd.oasis.opendocument.spreadsheet": "ods",
       "application/vnd.oasis.opendocument.presentation": "odp"}
MAX_BYTES = 512 * 1024 * 1024
MAX_PIXELS = 150_000_000
MAX_PAGES = 500


def xml(data: bytes) -> ET.Element:
    if len(data) > 32 * 1024 * 1024 or b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ConversionError("XML demasiado grande o con entidades externas no admitidas.")
    return ET.fromstring(data)


def zip_format(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        infos = z.infolist()
        if len(infos) > 20000 or sum(i.file_size for i in infos) > 1024 ** 3:
            raise ConversionError("El documento comprimido excede el límite de seguridad (1 GiB expandido).")
        if any(i.flag_bits & 1 for i in infos):
            raise ConversionError("No se admiten documentos cifrados.")
        for part, fmt in ZIP_FORMATS.items():
            if part in z.namelist():
                if "[Content_Types].xml" not in z.namelist():
                    break
                xml(z.read("[Content_Types].xml"))
                xml(z.read(part))
                return fmt
        if "mimetype" in z.namelist():
            fmt = ODF.get(z.read("mimetype").decode().strip())
            if fmt and "content.xml" in z.namelist():
                xml(z.read("content.xml"))
                return fmt
    raise ConversionError("El archivo ZIP no es un documento Office compatible.")


def pdf_metadata(path: Path) -> tuple[int, bool]:
    import shutil
    if not shutil.which("pdfinfo"):
        raise ConversionError("Falta pdfinfo (poppler-utils) para validar PDF.")
    info = run(["pdfinfo", str(path)], timeout=15)
    if re.search(r"^Encrypted:\s+yes", info, re.M):
        raise ConversionError("El PDF está cifrado; guárdalo sin contraseña antes de convertirlo.")
    match = re.search(r"^Pages:\s+(\d+)", info, re.M)
    pages = int(match[1]) if match else 0
    if not 1 <= pages <= MAX_PAGES:
        raise ConversionError(f"PDF sin páginas o con más de {MAX_PAGES} páginas.")
    return pages, False


def detect(path: Path, *, probe_pdf_text: bool = True, analyze_pdf: bool = True, check_cancel=None) -> Source:
    path = Path(os.path.abspath(path.expanduser()))
    try:
        st = path.lstat()
        if not stat.S_ISREG(st.st_mode):
            raise ConversionError("Selecciona un archivo regular; los enlaces simbólicos no se convierten.")
        if not 0 < st.st_size <= MAX_BYTES:
            raise ConversionError("El archivo está vacío o excede el límite de 512 MiB.")
        with path.open("rb") as f:
            head = f.read(8192)
        mime = QMimeDatabase().mimeTypeForFile(str(path), QMimeDatabase.MatchContent).name()
        if head.startswith(b"%PDF-"):
            pages, _ = pdf_metadata(path)
            import shutil
            text = False
            if probe_pdf_text and shutil.which("pdftotext"):
                # Inspect every page: a PDF may have a scanned cover but selectable text later.
                text = bool(run(["pdftotext", "-enc", "UTF-8", str(path), "-"], timeout=20).strip())
            profile = None
            from .capabilities import module_available
            if analyze_pdf and module_available("pymupdf"):
                from .pdf_analysis import inspect_pdf
                try:
                    profile = inspect_pdf(path, check_cancel)
                except ConversionError:
                    raise
                except Exception as e:
                    raise ConversionError(f"No se pudo analizar la estructura PDF: {e}") from e
                text = any(p.text_chars for p in profile.pages)
            return Source(path, "pdf", "application/pdf", pages, text, pdf=profile)
        if head.startswith(b"PK"):
            return Source(path, zip_format(path), mime)
        if head.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
            import olefile
            with olefile.OleFileIO(path) as ole:
                fmt = next((fmt for part, fmt in (("WordDocument", "doc"), ("Workbook", "xls"),
                           ("Book", "xls"), ("PowerPoint Document", "ppt")) if ole.exists(part)), None)
            if fmt:
                return Source(path, fmt, mime)
            raise ConversionError("Contenedor OLE no admitido o documento cifrado.")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(path) as im:
                    fmt = IMAGE_FORMATS.get(im.format)
                    frames = getattr(im, "n_frames", 1)
                    if not fmt:
                        raise ConversionError("Este formato de imagen no está implementado.")
                    if frames > MAX_PAGES or im.width * im.height * frames > MAX_PIXELS:
                        raise ConversionError("Imagen demasiado grande o con demasiados cuadros.")
                    im.verify()
                return Source(path, fmt, mime, frames)
        except UnidentifiedImageError:
            pass
        text = codecs.getincrementaldecoder("utf-8-sig")().decode(head, final=st.st_size <= len(head))
        if "\x00" in text or any(ord(c) < 9 or 13 < ord(c) < 32 for c in text):
            raise ConversionError("Contenido binario no compatible.")
        ext = path.suffix.lower().lstrip(".")
        if text.lstrip().startswith("{\\rtf"):
            fmt = "rtf"
        elif re.search(r"<\s*(?:!doctype\s+html|html|head|body)(?:\s|>)", text, re.I):
            fmt = "html"
        elif ext in ("md", "markdown"):
            fmt = "md"
        elif ext in ("csv", "tsv"):
            delimiter = "\t" if ext == "tsv" else csv.Sniffer().sniff(text, delimiters=",;\t|").delimiter
            rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
            if not rows or max(map(len, rows)) < 2:
                raise ConversionError("No se detectaron columnas en la tabla de texto.")
            fmt = ext
        elif ext in ("txt", "text") or mime == "text/plain" and ext not in (
                "docx", "odt", "xlsx", "ods", "pptx", "odp", "pdf", "doc", "xls", "ppt",
                "png", "jpg", "jpeg", "gif", "webp", "bmp", "tiff", "rtf", "html"):
            fmt = "txt"
        else:
            raise ConversionError("El contenido no coincide con un formato compatible.")
        notes = ("Los recursos vinculados fuera del archivo no se incorporan; usa imágenes incrustadas.",) if fmt in ("md", "html") else ()
        return Source(path, fmt, mime, warnings=notes)
    except ConversionError:
        raise
    except (OSError, ValueError, UnicodeError, zipfile.BadZipFile, ET.ParseError, csv.Error,
            Image.DecompressionBombError, Image.DecompressionBombWarning, ImportError) as e:
        raise ConversionError(f"No se puede leer o validar el archivo: {e}") from e

