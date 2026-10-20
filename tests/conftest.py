import os
import zipfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image

from convertix.config import Preferences
from convertix.models import Source
from convertix.registry import office_filters, FILTERS
from convertix.service import convert

MARKER = "Convertix café 日本 123"
NS = '''xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" xmlns:presentation="urn:oasis:names:tc:opendocument:xmlns:presentation:1.0" xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0" office:version="1.3"'''


def odf(path: Path, kind: str) -> Path:
    mime = "application/vnd.oasis.opendocument." + {"odt": "text", "ods": "spreadsheet", "odp": "presentation"}[kind]
    if kind == "odt":
        body = f'<office:text><text:h text:outline-level="1">{MARKER}</text:h><text:p>Texto con estilos y una tabla.</text:p><table:table table:name="Datos"><table:table-column/><table:table-row><table:table-cell office:value-type="string"><text:p>Contenido tabular 42</text:p></table:table-cell></table:table-row></table:table></office:text>'
    elif kind == "ods":
        cell = f'<table:table-row><table:table-cell office:value-type="string"><text:p>{MARKER}</text:p></table:table-cell><table:table-cell office:value-type="float" office:value="42"><text:p>42</text:p></table:table-cell></table:table-row>'
        body = f'<office:spreadsheet><table:table table:name="Primera"><table:table-column table:style-name="co1" table:number-columns-repeated="2"/>{cell}</table:table><table:table table:name="Segunda"><table:table-column table:style-name="co1" table:number-columns-repeated="2"/>{cell}</table:table></office:spreadsheet>'
    else:
        pages = ''.join(f'<draw:page draw:name="Diapositiva{i}" draw:master-page-name="Default"><draw:frame svg:x="1cm" svg:y="1cm" svg:width="24cm" svg:height="5cm"><draw:text-box><text:p>{MARKER} · {i}</text:p></draw:text-box></draw:frame></draw:page>' for i in (1, 2))
        body = f'<office:presentation>{pages}</office:presentation>'
    automatic = '<office:automatic-styles><style:style style:name="co1" style:family="table-column"><style:table-column-properties style:column-width="8cm"/></style:style></office:automatic-styles>' if kind == "ods" else ''
    content = f'<?xml version="1.0" encoding="UTF-8"?><office:document-content {NS}>{automatic}<office:body>{body}</office:body></office:document-content>'
    styles = f'''<?xml version="1.0"?><office:document-styles {NS}><office:automatic-styles><style:page-layout style:name="pm1"><style:page-layout-properties fo:page-width="28cm" fo:page-height="21cm" style:print-orientation="landscape"/></style:page-layout></office:automatic-styles><office:master-styles><style:master-page style:name="Default" style:page-layout-name="pm1"/></office:master-styles></office:document-styles>'''
    manifest = f'''<?xml version="1.0"?><manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"><manifest:file-entry manifest:full-path="/" manifest:media-type="{mime}"/><manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/><manifest:file-entry manifest:full-path="styles.xml" manifest:media-type="text/xml"/></manifest:manifest>'''
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", mime, compress_type=zipfile.ZIP_STORED)
        z.writestr("content.xml", content)
        z.writestr("styles.xml", styles)
        z.writestr("META-INF/manifest.xml", manifest)
    return path


@pytest.fixture(scope="session")
def samples(tmp_path_factory):
    folder = tmp_path_factory.mktemp("convertix-synthetic")
    result = {kind: odf(folder/f"ejemplo.{kind}", kind) for kind in ("odt", "ods", "odp")}
    for fmt in ("png", "jpg", "webp", "bmp", "tiff", "gif"):
        p = folder/f"imagen.{fmt}"
        Image.new("RGB", (160, 90), (24, 80, 130)).save(p)
        result[fmt] = p
    for fmt, text in (("md", f"# {MARKER}\n\n**Texto en negrita**.\n"),
                      ("txt", MARKER+"\nOtra línea\n"),
                      ("csv", 'nombre,cantidad\n"café 日本",42\n"=2+2",7\n'),
                      ("tsv", "nombre\tcantidad\ncafé 日本\t42\n"),
                      ("html", f'<!doctype html><html><head><meta charset="UTF-8"></head><body><h1>{MARKER}</h1><p>Prueba</p></body></html>'),
                      ("rtf", r"{\rtf1\ansi Convertix cafe 123\par Texto}")):
        p = folder/f"ejemplo.{fmt}"; p.write_text(text); result[fmt] = p
    if FILTERS["docx"] in office_filters():
        for base, target in (("odt", "docx"), ("ods", "xlsx"), ("odp", "pptx")):
            result[target] = convert(result[base], target).outputs[0]
    result["pdf"] = convert(result["png"], "pdf").outputs[0]
    return result


@pytest.fixture
def qt_app():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QIcon
    app = QApplication.instance() or QApplication([])
    QIcon.setFallbackThemeName("breeze")
    yield app

