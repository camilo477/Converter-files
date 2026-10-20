"""Remove JPEG metadata segments without decoding/recompressing image data."""
from ..models import ConversionError


def copy_scan(input_file, output):
    """Copy entropy coding up to the next segment, respecting stuffing/restart markers."""
    import re
    carry = b""
    while chunk := input_file.read(65536):
        data = carry+chunk
        for match in re.finditer(b"\xff([^\x00\xff])", data):
            if not 0xD0 <= match[1][0] <= 0xD7:
                output.write(data[:match.start()])
                input_file.seek(-(len(data)-match.start()), 1)
                return
        if data.endswith(b"\xff"):
            output.write(data[:-1]); carry = b"\xff"
        else:
            output.write(data); carry = b""
    raise ConversionError("JPEG truncado dentro de los datos de imagen.")


def strip(source, destination, *, deep=False):
    with source.open("rb") as input_file, destination.open("xb") as output:
        if input_file.read(2) != b"\xff\xd8":
            raise ConversionError("Cabecera JPEG inválida.")
        output.write(b"\xff\xd8")
        while True:
            prefix = input_file.read(1)
            if prefix != b"\xff":
                raise ConversionError("Segmento JPEG inválido.")
            marker = input_file.read(1)
            while marker == b"\xff":
                marker = input_file.read(1)
            if not marker:
                raise ConversionError("JPEG truncado.")
            code = marker[0]
            if code == 0xD9:
                output.write(b"\xff"+marker)
                break
            if code in range(0xD0, 0xD8) or code == 0x01:
                output.write(b"\xff"+marker)
                continue
            length_bytes = input_file.read(2)
            if len(length_bytes) != 2:
                raise ConversionError("Longitud JPEG truncada.")
            length = int.from_bytes(length_bytes, "big")
            payload = input_file.read(max(0,length-2))
            if length < 2 or len(payload) != length-2:
                raise ConversionError("Segmento JPEG truncado.")
            keep = not (0xE0 <= code <= 0xEF or code == 0xFE)
            if code == 0xE0 and payload.startswith(b"JFIF\0"):
                # Keep the color-space identifier; strip any embedded thumbnail.
                payload = payload[:12]+b"\0\0"
                if deep and len(payload) >= 14:
                    payload = payload[:7]+b"\0\0\x01\0\x01\0\0"
                keep = True
            if code == 0xE2 and payload.startswith(b"ICC_PROFILE\0"):
                keep = True
            if code == 0xEE and payload.startswith(b"Adobe"):
                keep = True
            if keep:
                output.write(b"\xff"+marker+(len(payload)+2).to_bytes(2,"big")+payload)
            if code == 0xDA:
                # Continue parsing between progressive scans; don't retain late APP/COM segments.
                copy_scan(input_file, output)
