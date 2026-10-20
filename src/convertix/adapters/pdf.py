from pathlib import Path

from ..config import Preferences
from ..models import ConversionError, Source
from ..process import run


def convert(source: Source, target: str, output: Path, prefs: Preferences) -> None:
    if target == "txt":
        path = output / "document.txt"
        run(["pdftotext", "-layout", "-enc", "UTF-8", str(source.path), str(path)], timeout=prefs.timeout)
        if not path.read_text().strip():
            raise ConversionError("El PDF no contiene texto extraíble. Se necesitaría OCR.")
    else:
        args = ["pdftoppm", "-r", str(prefs.pdf_dpi), "-png" if target == "png" else "-jpeg"]
        if target == "jpg":
            args.extend(["-jpegopt", f"quality={prefs.quality}"])
        args.extend([str(source.path), str(output / "document-página")])
        run(args, timeout=prefs.timeout)

