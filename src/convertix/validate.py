import re
from pathlib import Path

from PIL import Image

from .detect import pdf_metadata, zip_format
from .models import ConversionError, Source
from .registry import IMAGES


def validate_resources(folder: Path, main: Path, target: str) -> None:
    from urllib.parse import unquote, urlsplit
    references = []
    if target == "html":
        from html.parser import HTMLParser
        class Images(HTMLParser):
            def handle_starttag(self, tag, attrs):
                if tag == "img":
                    references.extend(value for key, value in attrs if key == "src" and value)
        Images().feed(main.read_text(encoding="utf-8-sig"))
    elif target == "md":
        references.extend(re.findall(r'!\[[^\]]*\]\(([^\s)]+)\)', main.read_text(encoding="utf-8-sig")))
    for link in references:
        url = urlsplit(link)
        if url.scheme == "data":
            continue
        if url.scheme or url.netloc:
            raise ConversionError("El archivo generado referencia una imagen externa no incorporada.")
        asset = (main.parent/unquote(url.path)).resolve()
        if not asset.is_relative_to(folder.resolve()) or not asset.is_file():
            raise ConversionError("Un recurso del documento generado falta o apunta fuera del resultado.")


def validate_animation(path: Path, source: Source, target: str) -> None:
    with Image.open(source.path) as original, Image.open(path) as converted:
        for index in range(source.frames):
            original.seek(index); original.load()
            converted.seek(index); converted.load()
            duration = max(10, int(original.info.get("duration", 100)))
            actual = int(converted.info.get("duration", 100))
            if abs(duration-actual) > (9 if target == "gif" else 0):
                raise ConversionError("El motor no conservó la duración de la animación.")
            expected = original.convert("RGBA").getchannel("A")
            if target == "gif":
                expected = expected.point(lambda alpha: 255 if alpha >= 128 else 0)
            if expected.tobytes() != converted.convert("RGBA").getchannel("A").tobytes():
                raise ConversionError("El motor no conservó la transparencia compatible de todos los cuadros.")


def validate_outputs(folder: Path, target: str, source: Source) -> None:
    from .registry import extension
    target = extension(target)
    files = sorted(p for p in folder.rglob("*") if p.is_file())
    if not files or any(p.is_symlink() or p.stat().st_size == 0 for p in files):
        raise ConversionError("El motor generó archivos vacíos o enlaces no admitidos.")
    main = [p for p in files if p.suffix.lower() == "." + target]
    if not main:
        raise ConversionError("El motor no generó el formato solicitado.")
    for p in main:
        if target == "pdf":
            pages, _ = pdf_metadata(p)
            if source.format in IMAGES and pages != source.frames:
                raise ConversionError("El PDF no conserva todos los cuadros de la imagen.")
        elif target in IMAGES:
            with Image.open(p) as im:
                actual = {"JPEG": "jpg", "TIFF": "tiff"}.get(im.format, im.format.lower())
                if actual != target:
                    raise ConversionError("La firma del archivo no coincide con su formato.")
                count = getattr(im, "n_frames", 1)
                for n in range(count):
                    im.seek(n)
                    im.load()
                animated = source.format in ("gif", "webp") and target in ("gif", "webp")
                if (target == "tiff" or animated) and source.format in IMAGES and source.frames > 1 and count != source.frames:
                    raise ConversionError("El TIFF no conserva todas las páginas.")
            if animated and source.frames > 1:
                validate_animation(p, source, target)
        elif target in ("docx", "odt", "xlsx", "ods", "pptx", "odp"):
            if zip_format(p) != target:
                raise ConversionError("El documento generado tiene una estructura inválida.")
        elif target in ("doc", "xls", "ppt"):
            from .detect import detect
            if detect(p, analyze_pdf=False).format != target:
                raise ConversionError("El documento binario de Office generado no es válido.")
        elif target == "rtf":
            if not p.read_bytes().lstrip().startswith(b"{\\rtf"):
                raise ConversionError("RTF generado inválido.")
        else:
            text = p.read_text(encoding="utf-8-sig")
            if target == "html" and not re.search(r"<html\b", text, re.I):
                raise ConversionError("HTML generado inválido.")
            if target in ("html", "md"):
                validate_resources(folder, p, target)
    if source.format == "pdf" and target in IMAGES and len(main) != source.frames:
        raise ConversionError("No se exportaron todas las páginas del PDF.")
    animated = source.format in ("gif", "webp") and target in ("gif", "webp")
    if source.format in IMAGES and source.frames > 1 and target in IMAGES - {"tiff"} and not animated and len(main) != source.frames:
        raise ConversionError("No se exportaron todos los cuadros de la imagen.")
