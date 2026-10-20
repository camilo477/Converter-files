"""Content-aware editing actions, separate from conversion destinations."""
import shutil
from ..capabilities import module_available

IMAGES = {"jpg", "png", "webp", "tiff", "bmp", "gif"}
LABELS = {
    "pdf-merge": ("Unir PDFs", "document-multiple", "Ordena o añade documentos; conserva las páginas sin rasterizarlas."),
    "pdf-split": ("Dividir PDF", "edit-cut", "Extrae páginas o crea partes por intervalos y rangos."),
    "optimize": ("Optimizar", "document-save", "Reduce tamaño manteniendo el formato. El ahorro depende del archivo."),
    "archive": ("Crear ZIP / 7z", "package-x-generic", "Crea un archivo comprimido; el tamaño puede aumentar."),
    "crop": ("Recortar", "transform-crop", "Selecciona una región en la imagen orientada."),
    "resize": ("Redimensionar", "transform-scale", "Cambia dimensiones; ampliar interpola, no añade detalle real."),
    "images-pdf": ("Crear PDF", "application-pdf", "Una página por imagen; permite ordenar y configurar las páginas."),
    "metadata": ("Metadatos", "edit-clear", "Genera copias limpias. No borra contenido visible ni garantiza anonimato."),
}


def available(sources):
    if not sources:
        return []
    formats = {s.format for s in sources}
    pdf = module_available("pymupdf")
    actions = []
    if formats == {"pdf"} and pdf:
        actions += ["pdf-merge"]
        if len(sources) == 1:
            actions += ["pdf-split"]
    if formats <= {"pdf", "jpg", "png", "webp"} and ("pdf" not in formats or pdf):
        actions += ["optimize"]
    if len(sources) == 1 and formats <= IMAGES and sources[0].frames == 1:
        actions += ["crop"]
    if formats <= IMAGES:
        actions += ["resize"]
        if pdf and all(s.frames == 1 for s in sources):
            actions += ["images-pdf"]
    if formats <= {"jpg", "png", "webp", "tiff", "pdf"} and ("pdf" not in formats or pdf):
        actions += ["metadata"]
    actions += ["archive"]
    return [{"target": "tool:"+a, "label": LABELS[a][0], "icon": LABELS[a][1],
             "hint": LABELS[a][2], "accent": "#6fb7b2"} for a in actions]


def archive_formats():
    return ["zip"] + (["7z"] if shutil.which("7z") or shutil.which("7zz") else [])
