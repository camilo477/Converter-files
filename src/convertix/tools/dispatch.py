"""Worker-only tool dispatch and preview requests."""
from pathlib import Path
from ..models import ConversionError


def execute(data, folder):
    action = data["action"]
    paths = [Path(p) for p in data["sources"]]
    params = data.get("params", {})
    def progress(message):
        (folder/"progress.txt").write_text(message)
    if action == "__inspect__":
        from .inspection import inspect_file
        return {"items": [inspect_file(p) for p in paths]}
    if action == "__thumbnail__":
        from .inspection import thumbnail
        thumbnail(paths[0], params, folder/"preview.png")
        return {}
    if not paths or (action not in ("pdf-merge", "images-pdf", "archive") and len(paths) != 1):
        raise ConversionError("La herramienta requiere una selección individual por trabajo.")
    output = folder/"output"
    output.mkdir(mode=0o700)
    if action in ("pdf-merge", "pdf-split"):
        from .pdf_ops import merge, split
        return (merge if action == "pdf-merge" else split)(paths, params, output, progress)
    if action == "optimize":
        with paths[0].open("rb") as handle:
            pdf = handle.read(5) == b"%PDF-"
        if pdf:
            from .pdf_ops import optimize
        else:
            from .image_ops import optimize
        return optimize(paths, params, output, progress)
    if action in ("crop", "resize"):
        from .image_ops import edit
        return edit(action, paths, params, output, progress)
    if action == "images-pdf":
        from .images_pdf import combine
        return combine(paths, params, output, progress)
    if action == "metadata":
        from .metadata import clean
        return clean(paths, params, output, progress)
    if action == "archive":
        from .archive import create
        return create(paths, params, output, progress)
    raise ConversionError("Herramienta desconocida.")
