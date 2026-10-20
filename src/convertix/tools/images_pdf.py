"""Ordered image composition with explicit geometry and a white transparency matte."""
import io
from pathlib import Path
from PIL import Image, ImageOps
from ..models import ConversionError
from ..detect import MAX_PAGES, MAX_PIXELS
from .pdf_ops import save, verify_pdf


def combine(paths, params, output, progress):
    import pymupdf
    if not 1 <= len(paths) <= MAX_PAGES:
        raise ConversionError("Selecciona entre 1 y 500 imágenes.")
    page_mode = params.get("page_size", "a4")
    if page_mode not in ("a4", "letter", "image", "custom"):
        raise ConversionError("Tamaño de página desconocido.")
    orientation = params.get("orientation", "auto")
    fit = params.get("fit", "contain")
    if orientation not in ("auto", "portrait", "landscape") or fit not in ("contain", "cover", "natural"):
        raise ConversionError("Ajuste u orientación desconocidos.")
    margin = float(params.get("margin_mm", 8))*72/25.4
    if not 0 <= margin <= 200:
        raise ConversionError("El margen solicitado está fuera de límites.")
    sizes = []
    with pymupdf.open() as doc:
        for i, path in enumerate(paths):
            progress(f"Componiendo página {i+1}/{len(paths)}")
            with Image.open(path) as image:
                if getattr(image, "n_frames", 1) != 1:
                    raise ConversionError("Crear PDF no admite animaciones ni imágenes multipágina; usa la conversión habitual para conservar todos los cuadros.")
                if image.width*image.height > MAX_PIXELS:
                    raise ConversionError("Imagen demasiado grande.")
                oriented = ImageOps.exif_transpose(image)
                iw, ih = oriented.size
                dpi = image.info.get("dpi", (96, 96))
                dx, dy = [min(1200, max(36, float(x or 96))) for x in dpi[:2]]
                natural_w, natural_h = iw*72/dx, ih*72/dy
                pw, ph = {"a4": (595.276, 841.89), "letter": (612, 792),
                          "image": (natural_w+2*margin, natural_h+2*margin),
                          "custom": (float(params.get("page_width_mm", 210))*72/25.4,
                                     float(params.get("page_height_mm", 297))*72/25.4)}[page_mode]
                landscape = (iw > ih) if orientation == "auto" else orientation == "landscape"
                if landscape != (pw > ph):
                    pw, ph = ph, pw
                if not 20 <= pw <= 14400 or not 20 <= ph <= 14400 or 2*margin >= min(pw, ph):
                    raise ConversionError("Página o márgenes inválidos.")
                page = doc.new_page(width=pw, height=ph)
                area = pymupdf.Rect(margin, margin, pw-margin, ph-margin)
                ratio = max(area.width/iw, area.height/ih) if fit == "cover" else min(area.width/iw, area.height/ih)
                if fit == "natural":
                    ratio = min(ratio, 72/max(dx, dy))
                if fit == "cover":
                    # Crop image coordinates before embedding; no content outside the printable area.
                    cw, ch = area.width/ratio, area.height/ratio
                    oriented = oriented.crop(((iw-cw)/2, (ih-ch)/2, (iw+cw)/2, (ih+ch)/2))
                    target = area
                else:
                    w, h = iw*ratio, ih*ratio
                    target = pymupdf.Rect((pw-w)/2, (ph-h)/2, (pw+w)/2, (ph+h)/2)
                if image.format == "JPEG" and image.getexif().get(274, 1) == 1 and fit != "cover":
                    data = path.read_bytes()  # Preserve original JPEG bitstream when no rotation/crop is needed.
                else:
                    if "A" in oriented.getbands() or oriented.mode == "P":
                        rgba = oriented.convert("RGBA")
                        rgb = Image.new("RGB", rgba.size, "white")
                        rgb.paste(rgba, mask=rgba.getchannel("A"))
                    else:
                        rgb = oriented.convert("RGB")
                    buffer = io.BytesIO()
                    rgb.save(buffer, "PNG", icc_profile=image.info.get("icc_profile"))
                    data = buffer.getvalue()
                page.insert_image(target, stream=data, keep_proportion=False)
                sizes.append((pw, ph))
        result = output/"imagenes.pdf"
        save(doc, result)
    verify_pdf(result, sizes)
    return {"name": "imagenes.pdf", "summary": f"PDF creado · {len(paths)} imágenes en el orden elegido"}
