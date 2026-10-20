from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class PdfPageInfo:
    kind: str
    text_chars: int = 0
    tables: int = 0
    scan_tables: int = 0
    needs_ocr: bool = False


@dataclass(frozen=True)
class PdfProfile:
    kind: str
    pages: tuple[PdfPageInfo, ...]

    @property
    def needs_ocr(self) -> bool:
        return any(p.needs_ocr for p in self.pages)

    @property
    def tables(self) -> int:
        return sum(p.tables for p in self.pages)

    @property
    def scan_tables(self) -> int:
        return sum(p.scan_tables for p in self.pages)


class ConversionError(Exception):
    """An actionable error that can be shown without a Python traceback."""


class Cancelled(ConversionError):
    pass


@dataclass(frozen=True)
class Source:
    path: Path
    format: str
    mime: str
    frames: int = 1
    has_text: bool = False
    warnings: tuple[str, ...] = ()
    pdf: PdfProfile | None = None


@dataclass(frozen=True)
class Route:
    target: str
    engine: str
    description: str
    warning: str = ""


@dataclass
class Result:
    source: Path
    target: str
    outputs: list[Path] = field(default_factory=list)
    location: Path | None = None

