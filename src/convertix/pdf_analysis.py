"""Per-page PDF profiling and conservative ruled-table recognition for scanned pages.

Native table detection is delegated to MuPDF. Raster grids are only accepted when
connected horizontal/vertical rulings form at least two rows and two columns.
Paragraph alignment alone is never treated as a scanned table.
"""
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PIL import Image, ImageStat

from .models import ConversionError, PdfPageInfo, PdfProfile


@dataclass
class TableData:
    bbox: tuple[float, float, float, float]
    rows: list[list[str]]

    @property
    def usable(self) -> bool:
        return (len([r for r in self.rows if any(c.strip() for c in r)]) >= 2
                and max((len(r) for r in self.rows), default=0) >= 2
                and sum(bool(c.strip()) for r in self.rows for c in r) >= 3)


@dataclass
class Grid:
    xs: list[float]
    ys: list[float]

    @property
    def bbox(self):
        return self.xs[0], self.ys[0], self.xs[-1], self.ys[-1]


def thumbnail(page) -> Image.Image:
    import pymupdf
    scale = min(1.5, 1100/max(page.rect.width, page.rect.height))
    pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), colorspace=pymupdf.csGRAY, alpha=False)
    return Image.frombytes("L", (pix.width, pix.height), pix.samples)


def text_like(image: Image.Image) -> bool:
    histogram = image.histogram()
    dark = sum(histogram[:150]) / (image.width*image.height)
    return 0.0005 < dark < 0.55 and ImageStat.Stat(image).stddev[0] > 12


def _rulings(image: Image.Image, minimum: int) -> list[tuple[int, int, int]]:
    pixels = image.tobytes()
    width = image.width
    lines = []
    for y in range(image.height):
        start = None
        row = pixels[y*width:(y+1)*width]
        best = None
        for x, pixel in enumerate(row + b"\xff"):
            if pixel < 155 and start is None:
                start = x
            elif pixel >= 155 and start is not None:
                if x-start >= minimum and (best is None or x-start > best[2]-best[1]):
                    best = (y, start, x-1)
                start = None
        if best:
            if lines and y-lines[-1][0] <= 3 and abs(best[1]-lines[-1][1]) < 8 and abs(best[2]-lines[-1][2]) < 8:
                continue
            lines.append(best)
    return lines


def raster_grids(page, image: Image.Image | None = None) -> list[Grid]:
    image = image or thumbnail(page)
    horizontal = _rulings(image, max(45, image.width//5))
    vertical = _rulings(image.transpose(Image.Transpose.TRANSPOSE), max(30, image.height//14))
    nodes = [("h", *line) for line in horizontal] + [("v", *line) for line in vertical]
    if len(nodes) > 200:
        return []
    neighbours = [set() for _ in nodes]
    for i, (y, left, right) in enumerate(horizontal):
        for k, (x, top, bottom) in enumerate(vertical):
            j = len(horizontal)+k
            if left-3 <= x <= right+3 and top-3 <= y <= bottom+3:
                neighbours[i].add(j); neighbours[j].add(i)
    grids = []
    seen = set()
    for start in range(len(nodes)):
        if start in seen:
            continue
        group = set(); pending = [start]
        while pending:
            node = pending.pop()
            if node in group:
                continue
            group.add(node); seen.add(node); pending.extend(neighbours[node]-group)
        ys = sorted({nodes[i][1] for i in group if nodes[i][0] == "h"})
        xs = sorted({nodes[i][1] for i in group if nodes[i][0] == "v"})
        if len(ys) >= 3 and len(xs) >= 3:
            # Rendered coordinates are normalized to the unrotated page before conversion.
            grids.append(Grid([x*page.rect.width/image.width for x in xs],
                              [y*page.rect.height/image.height for y in ys]))
    return grids


def native_tables(page) -> list[TableData]:
    import pymupdf
    pymupdf.no_recommend_layout()
    # Do not trigger optional layout-model downloads. MuPDF's deterministic line detector is local.
    found = page.find_tables(strategy="lines")
    result = []
    for table in found.tables:
        rows = [[str(value) if value is not None else "" for value in row] for row in table.extract()]
        data = TableData(tuple(table.bbox), rows)
        if data.usable:
            result.append(data)
    return result


def scanned_tables(page) -> list[TableData]:
    import pymupdf
    result = []
    for grid in raster_grids(page):
        rows = [[page.get_textbox(pymupdf.Rect(x0+1, y0+1, x1-1, y1-1)).strip()
                 for x0, x1 in zip(grid.xs, grid.xs[1:])]
                for y0, y1 in zip(grid.ys, grid.ys[1:])]
        data = TableData(grid.bbox, rows)
        if data.usable:
            result.append(data)
    return result


def inspect_pdf(path: Path, check_cancel: Callable[[], None] | None = None) -> PdfProfile:
    import pymupdf
    started = time.monotonic()
    pages = []
    with pymupdf.open(path) as document:
        for page in document:
            if check_cancel:
                check_cancel()
            if time.monotonic()-started > 45:
                raise ConversionError("El análisis PDF superó 45 segundos; divide el documento antes de convertir.")
            text = page.get_text().strip()
            readable = sum(c.isalnum() for c in text)
            traces = page.get_texttrace() if readable else []
            invisible = sum(len(t["chars"]) for t in traces if t["type"] == 3 or t.get("opacity", 1) < 0.1)
            prior_ocr = any("glyphless" in t["font"].lower() for t in traces) or invisible > max(5, readable*0.6)
            info = page.get_image_info()
            area = max(1, page.rect.get_area())
            coverage = max((pymupdf.Rect(i["bbox"]).get_area()/area for i in info), default=0)
            largest = max((pymupdf.Rect(i["bbox"]) for i in info), key=lambda r: r.get_area(), default=pymupdf.Rect())
            covered_text = sum(len(t["chars"]) for t in traces
                               if (pymupdf.Rect(t["bbox"]) & largest).get_area() > pymupdf.Rect(t["bbox"]).get_area()*0.5)
            sample = thumbnail(page) if coverage > 0.25 else None
            needs = (not prior_ocr and coverage > 0.25 and covered_text < 30
                     and sample is not None and text_like(sample))
            if prior_ocr:
                kind = "ocr"
            elif needs:
                kind = "mixed" if readable else "scanned"
            elif readable:
                kind = "digital"
            else:
                kind = "no_text"
            tables = len(native_tables(page)) if readable else 0
            grids = len(raster_grids(page, sample)) if needs or prior_ocr and sample is not None else 0
            pages.append(PdfPageInfo(kind, readable, tables, grids, needs))
    kinds = {p.kind for p in pages if p.kind != "no_text"}
    if not kinds:
        kind = "no_text"
    elif kinds == {"ocr"}:
        kind = "ocr"
    elif kinds == {"digital"}:
        kind = "digital"
    elif kinds == {"scanned"}:
        kind = "scanned"
    else:
        kind = "mixed"
    return PdfProfile(kind, tuple(pages))
