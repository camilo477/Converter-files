"""Bounded details and thumbnails; invoked only in a disposable process."""
import os
from pathlib import Path
from PIL import Image, ImageOps
from ..detect import detect
from .pdf_ops import open_pdf


def inspect_file(path):
    if path.is_dir() and not path.is_symlink():
        return {"format": "folder", "name": path.name, "size": 0, "pages": 0, "width": 0, "height": 0,
                "frames": 0, "metadata": [], "signed": False}
    try:
        source = detect(path, analyze_pdf=False, probe_pdf_text=False)
    except Exception:
        # Arbitrary regular files may be archived, never parsed as another format.
        if not path.is_file() or path.is_symlink():
            raise
        return {"format": "file", "name": path.name, "size": path.stat().st_size, "pages": 0,
                "width": 0, "height": 0, "frames": 1, "metadata": [], "signed": False}
    info = {"format": source.format, "name": path.name, "size": path.stat().st_size,
            "pages": source.frames if source.format == "pdf" else 0, "width": 0, "height": 0,
            "frames": source.frames, "metadata": [], "signed": False}
    current = path.stat()
    info["fingerprint"] = [current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns]
    if source.format == "pdf":
        with open_pdf(path) as doc:
            categories = []
            if any(doc.metadata.get(k) for k in ("author", "title", "subject", "keywords", "creator", "producer", "creationDate", "modDate")):
                categories += ["Campos del documento"]
            if doc.get_xml_metadata():
                categories += ["XMP"]
            if doc.embfile_count():
                categories += ["Archivos adjuntos"]
            if any(next(p.annots() or iter(()), None) for p in doc):
                categories += ["Anotaciones (pueden contener datos personales)"]
            if doc.is_form_pdf:
                categories += ["Formularios"]
            info.update(metadata=categories, signed=doc.get_sigflags() > 0)
    elif source.format in ("png", "jpg", "webp", "tiff", "gif", "bmp"):
        with Image.open(path) as image:
            # Orientation changes dimensions, without allocating a full rotated image here.
            w, h = image.size
            if image.getexif().get(274, 1) in (5, 6, 7, 8):
                w, h = h, w
            categories = []
            if image.getexif():
                categories += ["EXIF (puede incluir cámara/GPS)"]
            categories += [k for k in ("xmp", "icc_profile", "dpi", "comment") if image.info.get(k)]
            if getattr(image, "text", {}):
                categories += ["Campos textuales PNG"]
            info.update(width=w, height=h, metadata=categories, dpi=list(image.info.get("dpi", (96,96))))
    return info


def thumbnail(path, params, destination):
    from ..models import ConversionError
    info = inspect_file(path)
    size = min(1400, max(96, int(params.get("extent", 420))))
    if info["format"] == "pdf":
        with open_pdf(path) as doc:
            number = int(params.get("page", 0))
            if not 0 <= number < len(doc):
                raise ConversionError("Página fuera de límites.")
            page = doc[number]
            import pymupdf
            scale = size/max(page.rect.width, page.rect.height)
            page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).save(destination)
    elif info["width"]:
        with Image.open(path) as image:
            image.thumbnail((size, size), Image.Resampling.LANCZOS)
            oriented = ImageOps.exif_transpose(image)
            oriented.convert("RGBA").save(destination, "PNG")
    else:
        raise ConversionError("Este archivo no tiene vista previa.")
