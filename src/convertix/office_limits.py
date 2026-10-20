"""Reject XLS exports that cannot represent the source's populated grid."""
import csv
import re
import zipfile

from .detect import xml
from .models import ConversionError, Source


def _check(row: int, column: int) -> None:
    if row > 65536 or column > 256:
        raise ConversionError("XLS admite hasta 65 536 filas y 256 columnas por hoja. Esta tabla excede esos límites; usa XLSX u ODS. No se ha publicado una versión recortada.")


def validate_xls_capacity(source: Source) -> None:
    if source.format == "xlsx":
        with zipfile.ZipFile(source.path) as archive:
            for name in archive.namelist():
                if not re.fullmatch(r"xl/worksheets/[^/]+\.xml", name):
                    continue
                root = xml(archive.read(name))
                for cell in root.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c"):
                    match = re.fullmatch(r"([A-Z]+)(\d+)", cell.get("r", ""))
                    if match:
                        column = 0
                        for letter in match[1]: column = column*26+ord(letter)-64
                        _check(int(match[2]), column)
    elif source.format == "ods":
        ns = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
        office = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}"
        with zipfile.ZipFile(source.path) as archive:
            root = xml(archive.read("content.xml"))
            for table in root.iter(ns+"table"):
                row_index = 0
                for row in table.iter(ns+"table-row"):
                    repeated = int(row.get(ns+"number-rows-repeated", "1"))
                    column = 0
                    for cell in row:
                        count = int(cell.get(ns+"number-columns-repeated", "1"))
                        if cell.get(office+"value") is not None or cell.get(ns+"formula") or "".join(cell.itertext()).strip():
                            _check(row_index+repeated, column+count)
                        column += count
                    row_index += repeated
    elif source.format in ("csv", "tsv"):
        with source.path.open(encoding="utf-8-sig", newline="") as stream:
            sample = stream.read(8192); stream.seek(0)
            delimiter = "\t" if source.format == "tsv" else csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
            for index, row in enumerate(csv.reader(stream, delimiter=delimiter), 1):
                _check(index, len(row))
