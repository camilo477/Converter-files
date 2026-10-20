"""A small editable document model built from MuPDF text, images and real tables.

This is a reconstruction, not a pixel-identical PDF renderer. Two clear columns
are read separately; headings use font-size evidence, and code uses font flags.
"""
import io
import re
from dataclasses import dataclass, field

from PIL import Image

from .pdf_analysis import TableData, native_tables, scanned_tables


@dataclass
class Span:
    text: str
    size: float = 11
    font: str = "Arial"
    bold: bool = False
    italic: bool = False
    mono: bool = False
    color: int = 0
    url: str = ""


@dataclass
class Element:
    kind: str
    bbox: tuple
    spans: list[Span] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    image: bytes = b""
    level: int = 0
    column: int = 0

    @property
    def text(self):
        return "".join(s.text for s in self.spans)


@dataclass
class LayoutPage:
    width: float
    height: float
    elements: list[Element]
    columns: int = 1


def safe_uri(value: str) -> str:
    from urllib.parse import urlsplit
    return value if urlsplit(value).scheme.lower() in ("https", "http", "mailto") else ""


def ordered(elements: list[Element], width: float) -> tuple[list[Element], int]:
    mid = width/2
    for e in elements:
        e.column = -1 if e.bbox[2] < mid+3 else 1 if e.bbox[0] > mid-3 else 0
    if sum(e.column == -1 and e.kind == "text" for e in elements) < 2 or sum(e.column == 1 and e.kind == "text" for e in elements) < 2:
        for e in elements:
            e.column = 0
        return sorted(elements, key=lambda e: (e.bbox[1], e.bbox[0])), 1
    # Full-width headings/tables delimit reading bands: each left column precedes its right column.
    wide = sorted((e for e in elements if e.column == 0), key=lambda e: e.bbox[1])
    pending = [e for e in elements if e.column]
    result = []
    for boundary in wide + [None]:
        band = [e for e in pending if boundary is None or e.bbox[1] < boundary.bbox[1]]
        result.extend(sorted(band, key=lambda e: (e.column, e.bbox[1], e.bbox[0])))
        pending = [e for e in pending if e not in band]
        if boundary:
            result.append(boundary)
    return result, 2


def extract_page(page, *, from_scan: bool = False) -> LayoutPage:
    import pymupdf
    tables = native_tables(page)
    if from_scan:
        for table in scanned_tables(page):
            if not any((pymupdf.Rect(table.bbox) & pymupdf.Rect(t.bbox)).get_area() > pymupdf.Rect(table.bbox).get_area()*0.5 for t in tables):
                tables.append(table)
    elements = [Element("table", t.bbox, rows=t.rows) for t in tables]
    data = page.get_text("dict", flags=pymupdf.TEXTFLAGS_DICT)
    links = [link for link in page.get_links() if safe_uri(link.get("uri", ""))]
    weights = {}
    for block in data["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                size = round(span["size"], 1)
                weights[size] = weights.get(size, 0)+len(span["text"].strip())
    base = 11
    accumulated = 0
    for size, count in sorted(weights.items()):
        accumulated += count
        if accumulated >= sum(weights.values())/2:
            base = size
            break
    for block in data["blocks"]:
        if block["type"] == 1:
            rect = pymupdf.Rect(block["bbox"])
            # A scanned background is never advertised as the editable document itself.
            if rect.get_area() > page.rect.get_area()*0.75:
                continue
            if block.get("image"):
                with Image.open(io.BytesIO(block["image"])) as image:
                    if image.width*image.height > 150_000_000:
                        continue
                    buffer = io.BytesIO()
                    image.convert("RGBA").save(buffer, "PNG")
                elements.append(Element("image", tuple(rect), image=buffer.getvalue()))
            continue
        remaining = []
        for line in block.get("lines", []):
            rect = pymupdf.Rect(line["bbox"])
            if any((rect & pymupdf.Rect(t.bbox)).get_area() > max(1, rect.get_area())*0.5 for t in tables):
                continue
            spans = []
            for raw in line["spans"]:
                url = next((link["uri"] for link in links if (pymupdf.Rect(raw["bbox"]) & link["from"]).get_area() > 0), "")
                ocr_font = "glyphless" in raw["font"].lower()
                spans.append(Span(raw["text"], raw["size"], "Arial" if ocr_font else raw["font"].split("+")[-1],
                                  bool(raw["flags"] & 16), bool(raw["flags"] & 2),
                                  bool(raw["flags"] & 8) and not ocr_font, raw["color"], url))
            if not any(s.text.strip() for s in spans):
                continue
            # Keep paragraphs together when MuPDF groups them, but never join two columns.
            side = rect.x0 > page.rect.width/2
            size = max(s.size for s in spans)
            heading = 1 if size >= base*1.45 else 2 if size >= base*1.20 else 0
            key = (side, heading, any(s.mono for s in spans))
            if remaining and remaining[-1][0] == key:
                previous = remaining[-1][1]
                if rect.y0-previous.bbox[3] < max(12, size) and abs(rect.x0-previous.bbox[0]) < 30:
                    previous.spans.append(Span("\n" if key[2] else " "))
                    previous.spans.extend(spans)
                    previous.bbox = tuple(pymupdf.Rect(previous.bbox) | rect)
                    continue
            element = Element("text", tuple(rect), spans=spans, level=heading)
            remaining.append((key, element))
        elements.extend(e for _, e in remaining)
    result, columns = ordered(elements, page.rect.width)
    return LayoutPage(page.rect.width, page.rect.height, result, columns)


def list_style(text: str) -> str:
    if re.match(r"^\s*[•●◦\-*]\s+", text):
        return "List Bullet"
    if re.match(r"^\s*\d+[.)]\s+", text):
        return "List Number"
    return ""
