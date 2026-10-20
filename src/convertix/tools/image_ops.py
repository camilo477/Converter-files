"""Oriented image geometry, animation-aware resizing and format optimization."""
from pathlib import Path
from PIL import Image, ImageOps
from ..detect import MAX_PIXELS, MAX_PAGES
from ..models import ConversionError
from .pdf_ops import reduction

FORMATS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp", "TIFF": "tiff", "BMP": "bmp", "GIF": "gif"}


def load(path):
    with Image.open(path) as original:
        fmt = FORMATS.get(original.format)
        if not fmt:
            raise ConversionError("Formato de imagen no compatible.")
        count = getattr(original, "n_frames", 1)
        if count > MAX_PAGES:
            raise ConversionError("Demasiados cuadros de imagen.")
        info = dict(original.info)
        frames, durations, pixels = [], [], 0
        for i in range(count):
            original.seek(i)
            pixels += original.width*original.height
            if pixels > MAX_PIXELS:
                raise ConversionError("La imagen excede 150 millones de píxeles acumulados.")
            frame = ImageOps.exif_transpose(original.copy())
            frames.append(frame.convert("RGBA") if frame.mode in ("P", "LA", "PA") or "A" in frame.mode else frame.convert("RGB"))
            durations.append(int(original.info.get("duration", 100)))
        exif = original.getexif()
        if 274 in exif:
            del exif[274]
        if exif:
            info["exif"] = exif.tobytes()
        return fmt, frames, durations, info


def save(frames, durations, info, fmt, path, *, quality=95, lossless=True, clean=False, deep=False):
    # Encoder options are allowlisted. Never copy opaque PNG/TIFF metadata wholesale.
    options = {}
    if info.get("icc_profile"):
        options["icc_profile"] = info["icc_profile"]
    if info.get("dpi") and not deep and fmt in ("jpg", "png", "tiff", "bmp"):
        options["dpi"] = info["dpi"]
    if not clean:
        for key in ("exif", "xmp", "comment"):
            if info.get(key) and fmt in ("jpg", "webp", "png", "tiff"):
                options[key] = info[key]
    if fmt in ("jpg", "webp"):
        options["quality"] = quality
    if fmt == "jpg":
        options.update(optimize=True, progressive=True, subsampling=0)
        frames = [frames[0].convert("RGB")]
    if fmt == "png":
        options.update(optimize=True, compress_level=9)
    if fmt == "webp":
        options.update(lossless=lossless, method=6, kmin=1, kmax=1, exact=True)
    if fmt == "tiff":
        options["compression"] = "tiff_deflate"
    if fmt == "gif":
        palette_frames = []
        for frame in frames:
            rgba = frame.convert("RGBA")
            pal = rgba.convert("RGB").quantize(colors=255)
            pal.putpalette(pal.getpalette()[:765]+[0,0,0])
            pal.paste(255, mask=rgba.getchannel("A").point(lambda a: 255 if a < 128 else 0))
            pal.info.clear()
            palette_frames.append(pal)
        frames = palette_frames
        options.update(disposal=2, transparency=255, background=255, optimize=False)
    for frame in frames:
        frame.info.clear()
    if len(frames) > 1:
        options.update(save_all=True, append_images=frames[1:])
        if fmt != "tiff":
            options["duration"] = durations
            if "loop" in info:
                options["loop"] = info["loop"]
        if fmt == "png":
            options.update(disposal=0, blend=0)
            if info.get("default_image"):
                options["default_image"] = True
                options["duration"] = durations[1:]
    frames[0].save(path, {"jpg": "JPEG", "tiff": "TIFF"}.get(fmt, fmt.upper()), **options)
    with Image.open(path) as result:
        if getattr(result, "n_frames", 1) != len(frames):
            raise ConversionError("El codificador no conservó todos los cuadros; se descartó el resultado.")
        for i, frame in enumerate(frames):
            result.seek(i)
            result.load()
            if result.size != frame.size:
                raise ConversionError("El resultado no conserva las dimensiones solicitadas.")
            if len(frames) > 1 and fmt != "tiff":
                if fmt == "png" and info.get("default_image") and i == 0:
                    continue
                expected = durations[i]//10*10 if fmt == "gif" else durations[i]
                # WebP exposes frame timing after load().
                if abs(result.info.get("duration", expected)-expected) > 1:
                    raise ConversionError("Cambió inesperadamente el tiempo de una animación.")


def resize_size(width, height, params):
    percent = float(params.get("percent", 0))
    if percent:
        if not 0.1 <= percent <= 1000:
            raise ConversionError("El porcentaje debe estar entre 0,1 y 1000.")
        w, h = round(width*percent/100), round(height*percent/100)
    else:
        w, h = int(params.get("width", 0)), int(params.get("height", 0))
        if params.get("keep_aspect", True):
            scales = ([w/width] if w > 0 else []) + ([h/height] if h > 0 else [])
            if not scales:
                raise ConversionError("Introduce ancho, alto o porcentaje.")
            factor = min(scales)
            w, h = round(width*factor), round(height*factor)
    if not 1 <= w <= 30000 or not 1 <= h <= 30000 or w*h > MAX_PIXELS:
        raise ConversionError("Las dimensiones solicitadas están fuera de los límites de imagen.")
    return w, h


def edit(action, paths, params, output, progress):
    if len(paths) != 1:
        raise ConversionError("Cada trabajo de imagen requiere un archivo.")
    fmt, frames, durations, info = load(paths[0])
    stem = Path(params["original_names"][0]).stem
    progress("Procesando imagen orientada…")
    if action == "crop":
        if len(frames) != 1:
            raise ConversionError("Recortar está deshabilitado en imágenes animadas o multipágina.")
        box = params.get("box", [])
        if not isinstance(box, (list, tuple)) or len(box) != 4:
            raise ConversionError("Selecciona una región rectangular.")
        left, top, right, bottom = [int(round(float(x))) for x in box]
        w, h = frames[0].size
        if not 0 <= left < right <= w or not 0 <= top < bottom <= h:
            raise ConversionError("Coordenadas de recorte inválidas o fuera de la imagen.")
        frames = [frames[0].crop((left, top, right, bottom))]
        name = f"{stem}_recortada.{fmt}"
        summary = f"Imagen recortada · {right-left} × {bottom-top}"
    elif action == "resize":
        method = {"lanczos": Image.Resampling.LANCZOS, "bicubic": Image.Resampling.BICUBIC,
                  "nearest": Image.Resampling.NEAREST}.get(params.get("interpolation", "lanczos"))
        if method is None:
            raise ConversionError("Interpolación no compatible.")
        sizes = [resize_size(*frame.size, params) for frame in frames]
        if sum(w*h for w, h in sizes) > MAX_PIXELS:
            raise ConversionError("El resultado excedería 150 millones de píxeles acumulados.")
        frames = [frame.resize(size, method) for frame, size in zip(frames, sizes)]
        w, h = sizes[0]
        name = f"{stem}_{w}x{h}.{fmt}"
        summary = f"Imagen redimensionada · {w} × {h} · {len(frames)} cuadro(s)"
    else:
        raise ConversionError("Herramienta de imagen desconocida.")
    save(frames, durations, info, fmt, output/("imagen."+fmt), quality=int(params.get("quality", 95)))
    return {"name": name, "summary": summary}


def optimize(paths, params, output, progress):
    fmt, frames, durations, info = load(paths[0])
    if fmt not in ("jpg", "png", "webp"):
        raise ConversionError("Solo se optimizan JPG, PNG y WebP.")
    level = params.get("level", "lossless")
    if level not in ("lossless", "balanced", "maximum"):
        raise ConversionError("Nivel de optimización desconocido.")
    if fmt == "jpg" and level == "lossless":
        raise ConversionError("JPG necesita recodificación con pérdida; elige Equilibrado o Máximo.")
    if fmt == "png" and level != "lossless":
        # Explicit lossy modes quantize colors, including compatible alpha.
        frames = [f.convert("RGBA").quantize(colors=256 if level == "balanced" else 64,
                   method=Image.Quantize.FASTOCTREE).convert("RGBA") for f in frames]
    quality = int(params.get("quality", 82 if level == "balanced" else 55))
    if not 10 <= quality <= 100:
        raise ConversionError("La calidad debe estar entre 10 y 100.")
    path = output/("optimizada."+fmt)
    progress("Optimizando imagen; se conservan todos los cuadros…")
    save(frames, durations, info, fmt, path, quality=quality, lossless=level == "lossless")
    stats, summary = reduction(paths[0], path, level, params)
    return {"name": Path(params["original_names"][0]).stem+"_optimizado."+fmt, "summary": summary, "stats": stats}
