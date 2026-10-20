"""Disposable process: parsers, native libraries and external engines live here."""
import json
import sys
import traceback
from dataclasses import asdict
from pathlib import Path

from .config import Preferences
from .detect import detect
from .models import ConversionError
from .registry import routes
from .security import restrict_worker


def main() -> int:
    request = Path(sys.argv[1])
    data = json.loads(request.read_text())
    try:
        prefs = Preferences.from_dict(data["prefs"])
        restrict_worker(prefs.timeout)
        source = detect(Path(data["source"]))
        target = data["target"]
        if target == "__probe__":
            details = asdict(source)
            details["path"] = str(source.path)
            (request.parent/"result.json").write_text(json.dumps({"ok": True, "source": details}))
            return 0
        route = next((r for r in routes(source, prefs) if r.target == target), None)
        if route is None:
            raise ConversionError("Conversión no compatible con el contenido o los motores disponibles.")
        output = Path(data["output"])
        if route.engine == "libreoffice":
            from .adapters.office import convert
        elif route.engine == "pillow":
            from .adapters.images import convert
        elif route.engine == "pdf_documents":
            from .adapters.pdf_documents import convert
        else:
            from .adapters.pdf import convert
        convert(source, target, output, prefs)
        from .validate import validate_outputs
        validate_outputs(output, target, source)
        payload = {"ok": True}
    except Exception as e:
        payload = {"ok": False, "error": str(e), "detail": traceback.format_exc()[-12000:]}
    (request.parent / "result.json").write_text(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

