"""Lightweight module and OCR capability checks, without loading large PDF libraries in QML."""
import functools
import importlib.util
import os
import shutil
from dataclasses import dataclass

from .process import run


def module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


@dataclass(frozen=True)
class OcrCapability:
    executable: str | None
    languages: tuple[str, ...]

    def supports(self, requested: str) -> bool:
        return bool(self.executable) and set(requested.split("+")).issubset(self.languages)


@functools.lru_cache(maxsize=8)
def _ocr_capability(executable: str | None, data_prefix: str, stamp: int) -> OcrCapability:
    if not executable:
        return OcrCapability(None, ())
    try:
        output = run([executable, "--list-langs"], timeout=8)
        langs = tuple(line.strip() for line in output.splitlines() if line.strip() and not line.startswith("List "))
        return OcrCapability(executable, langs)
    except Exception:
        return OcrCapability(executable, ())


def ocr_capability() -> OcrCapability:
    exe = shutil.which("tesseract")
    return _ocr_capability(exe, os.environ.get("TESSDATA_PREFIX", ""), os.stat(exe).st_mtime_ns if exe else 0)


def pdf_dependencies() -> dict[str, bool]:
    return {name: module_available(name) for name in ("pymupdf", "docx", "openpyxl")}
