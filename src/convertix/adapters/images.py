from pathlib import Path

from PIL import Image, ImageOps

from ..config import Preferences
from ..models import Source


def opaque(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    background = Image.new("RGB", rgba.size, "white")
    background.paste(rgba, mask=rgba.getchannel("A"))
    return background


def convert(source: Source, target: str, output: Path, prefs: Preferences) -> None:
    name = {"jpg": "JPEG", "tiff": "TIFF"}.get(target, target.upper())
    with Image.open(source.path) as original:
        frames = []
        durations = []
        source_loop = original.info.get("loop")
        # Decode every frame: never quietly export only frame zero.
        for index in range(source.frames):
            original.seek(index)
            original.load()
            durations.append(max(10, int(original.info.get("duration", 100))))
            frame = ImageOps.exif_transpose(original.copy())
            frame.load()
            if target in ("jpg", "bmp", "pdf"):
                frame = opaque(frame)
            elif frame.mode not in ("RGB", "RGBA", "L", "LA", "P", "1"):
                frame = frame.convert("RGBA")
            frames.append(frame)
        kwargs = {}
        if target in ("jpg", "webp", "pdf"):
            kwargs["quality"] = prefs.quality
        if target in ("jpg", "webp", "png", "tiff"):
            if original.info.get("icc_profile"):
                kwargs["icc_profile"] = original.info["icc_profile"]
            exif = frames[0].getexif()
            if exif:
                kwargs["exif"] = exif.tobytes()
        dpi = original.info.get("dpi", (96, 96))
        if target in ("pdf", "jpg", "png", "tiff", "bmp"):
            kwargs["dpi"] = dpi
        animated = source.format in ("gif", "webp") and target in ("gif", "webp") and len(frames) > 1
        if animated:
            frames = [frame.convert("RGBA") for frame in frames]
            if target == "webp":
                # GIF counts repetitions after the initial play; WebP counts total plays.
                loop = 1 if source_loop is None else 0 if source_loop == 0 else source_loop+1
                # Independent keyframes avoid libwebp 1.6 dropping alpha on optimized animations.
                frames[0].save(output/"document.webp", "WEBP", save_all=True, append_images=frames[1:],
                               duration=durations, loop=loop, background=(0,0,0,0), lossless=True,
                               kmin=1, kmax=1, quality=prefs.quality)
            else:
                palette_frames = []
                for frame in frames:
                    rgba = frame.convert("RGBA")
                    palette = rgba.convert("RGB").quantize(colors=255)
                    palette.putpalette(palette.getpalette()[:765]+[0,0,0])
                    palette.paste(255, mask=rgba.getchannel("A").point(lambda alpha: 255 if alpha < 128 else 0))
                    palette.info.clear()
                    palette_frames.append(palette)
                loop_options = {} if source_loop == 1 else {"loop": 0 if not source_loop else source_loop-1}
                palette_frames[0].save(output/"document.gif", "GIF", save_all=True, append_images=palette_frames[1:],
                                       duration=durations, disposal=2, transparency=255, background=255,
                                       optimize=False, **loop_options)
        elif target in ("pdf", "tiff") and len(frames) > 1:
            frames[0].save(output / f"document.{target}", name, save_all=True,
                           append_images=frames[1:], **kwargs)
        else:
            for index, frame in enumerate(frames, 1):
                suffix = f"-página-{index:03}" if len(frames) > 1 else ""
                frame.save(output / f"document{suffix}.{target}", name, **kwargs)

