"""Verified metadata copies; never described as forensic anonymization."""
from pathlib import Path
from PIL import Image
from ..models import ConversionError
from .image_ops import load, save as save_image
from .pdf_ops import open_pdf, check_signatures, save, verify_pdf

FIELDS = ("author", "title", "subject", "keywords", "creator", "producer", "creationDate", "modDate")


def clean(paths, params, output, progress):
    path = paths[0]
    deep = params.get("metadata_mode", "standard") == "deep"
    progress("Eliminando metadatos seleccionados y verificando la copia…")
    with path.open("rb") as handle:
        pdf = handle.read(5) == b"%PDF-"
    verified = []
    if pdf:
        result = output/"limpio.pdf"
        with open_pdf(path) as doc:
            check_signatures(doc, params)
            sizes = [(p.rect.width, p.rect.height) for p in doc]
            # Explicit flags prevent scrub's destructive defaults (OCR text, links, fields, redactions).
            doc.scrub(attached_files=False, embedded_files=False, clean_pages=False,
                      hidden_text=False, javascript=deep, metadata=True, redactions=False,
                      remove_links=False, reset_fields=False, reset_responses=False,
                      thumbnails=deep, xml_metadata=True)
            if params.get("remove_attachments", False):
                for name in doc.embfile_names():
                    doc.embfile_del(name)
                for page in doc:
                    for annotation in list(page.annots() or []):
                        if annotation.type[0] == 17:  # PDF_ANNOT_FILE_ATTACHMENT
                            page.delete_annot(annotation)
            if deep:
                for xref in range(1, doc.xref_length()):
                    try:
                        keys = doc.xref_get_keys(xref)
                        for key in ("Metadata", "PieceInfo"):
                            if key in keys:
                                doc.xref_set_key(xref, key, "null")
                    except RuntimeError:
                        continue
                for page in doc:
                    for annotation in page.annots() or []:
                        # set_info ignores empty dates in some MuPDF versions; delete PDF keys explicitly.
                        for key in ("T", "Subj", "CreationDate", "M"):
                            doc.xref_set_key(annotation.xref, key, "null")
            doc.set_metadata({})
            doc.del_xml_metadata()
            save(doc, result)  # Full rewrite + garbage collection: no retained incremental revisions.
        verify_pdf(result, sizes)
        with open_pdf(result) as doc:
            if any(doc.metadata.get(key) for key in FIELDS) or doc.get_xml_metadata():
                raise ConversionError("Persisten metadatos PDF seleccionados; no se publicó.")
            verified = ["Campos del documento", "XMP del documento"]
            if params.get("remove_attachments", False):
                if doc.embfile_count() or any(a.type[0] == 17 for p in doc for a in p.annots() or []):
                    raise ConversionError("No se pudieron eliminar todos los adjuntos seleccionados.")
                verified += ["Adjuntos"]
            if deep:
                for xref in range(1, doc.xref_length()):
                    try:
                        if doc.xref_get_key(xref, "Metadata")[0] not in ("null", "none"):
                            raise ConversionError("Persiste XMP asociado a objetos PDF.")
                    except RuntimeError:
                        continue
                if any(a.info.get(k) for p in doc for a in p.annots() or [] for k in ("title", "subject", "creationDate", "modDate")):
                    raise ConversionError("Persisten datos de autor/fecha en anotaciones.")
                verified += ["XMP de objetos", "Autor y fechas de anotaciones"]
        fmt = "pdf"
    else:
        fmt, frames, durations, info = load(path)
        if fmt not in ("jpg", "png", "webp", "tiff"):
            raise ConversionError("La limpieza admite JPG, PNG, WebP, TIFF y PDF.")
        result = output/("limpia."+fmt)
        with Image.open(path) as original:
            needs_rotation = original.getexif().get(274, 1) != 1
        if fmt == "jpg" and not needs_rotation:
            from .jpeg_metadata import strip
            strip(path, result, deep=deep)
        else:
            save_image(frames, durations, info, fmt, result, quality=100, lossless=True, clean=True, deep=deep)
        with Image.open(result) as image:
            for i in range(getattr(image, "n_frames", 1)):
                image.seek(i)
                exif = image.getexif()
                # TIFF's structural tags are essential for decoding; personal EXIF is forbidden.
                allowed_tiff = {256,257,258,259,262,273,274,277,278,279,282,283,284,296,317,320,338,339,34675}
                if (set(exif)-allowed_tiff if fmt == "tiff" else set(exif)) or image.info.get("xmp") or image.info.get("comment") or getattr(image, "text", {}):
                    raise ConversionError("Persisten metadatos personales en la imagen; no se publicó.")
        verified = ["EXIF personal/GPS", "XMP", "Comentarios y campos textuales"]
    name = Path(params["original_names"][0]).stem+"_sin_metadatos."+fmt
    return {"name": name, "summary": "Copia limpia · comprobados: "+", ".join(verified),
            "stats": {"verified_categories": verified, "mode": "deep" if deep else "standard",
                      "retained": "ICC; DPI en modo estándar. En PDF se conserva contenido visible, formularios, enlaces y OCR."}}
