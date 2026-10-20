"""Reject ambiguous JSON flags and non-finite geometry before doing any work."""
import math
from ..models import ConversionError


def validate(params):
    for key in ("allow_signed", "keep_larger", "remove_attachments", "keep_aspect"):
        if key in params and type(params[key]) is not bool:
            raise ConversionError(f"La opción {key} debe ser un booleano JSON (true/false).")
    for key in ("width", "height", "percent", "quality", "interval", "compression", "margin_mm", "page_width_mm", "page_height_mm"):
        if key in params and (type(params[key]) not in (int, float) or not math.isfinite(params[key])):
            raise ConversionError(f"La opción {key} debe ser un número finito.")
    if "fingerprints" in params and not isinstance(params["fingerprints"], dict):
        raise ConversionError("La comprobación de originales no es válida.")
    if params.get("metadata_mode", "standard") not in ("standard", "deep"):
        raise ConversionError("Modo de limpieza desconocido.")
