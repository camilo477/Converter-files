import argparse
import json
import logging
import os
import sys
from pathlib import Path

from . import __version__
from .config import load
from .detect import detect
from .models import ConversionError
from .registry import diagnostics, routes
from .service import convert
from .probe import probe


def setup_logging():
    folder = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "convertix"
    try:
        from logging.handlers import RotatingFileHandler
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        handler = RotatingFileHandler(folder / "convertix.log", maxBytes=1024*1024, backupCount=2)
        os.chmod(folder / "convertix.log", 0o600)
    except OSError:
        handler = logging.NullHandler()
    class JsonFormatter(logging.Formatter):
        def format(self, record):
            return json.dumps({"time": self.formatTime(record), "level": record.levelname,
                               "event": record.getMessage()}, ensure_ascii=False)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("convertix")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def main() -> int:
    parser = argparse.ArgumentParser(prog="convertix", description="Conversor local de archivos para KDE")
    parser.add_argument("files", nargs="*", type=Path)
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--diagnose", action="store_true")
    parser.add_argument("--list", action="store_true", help="Mostrar destinos compatibles sin interfaz")
    parser.add_argument("--to", help="Convertir sin interfaz al formato indicado")
    parser.add_argument("--timeout", type=int, help="Límite por archivo en segundos (10–1800)")
    args = parser.parse_args()
    if args.diagnose:
        print(json.dumps(diagnostics(), ensure_ascii=False, indent=2))
        return 0
    setup_logging()
    if args.list or args.to:
        if not args.files:
            parser.error("Selecciona al menos un archivo.")
        prefs = load()
        if args.timeout is not None:
            prefs.timeout = max(10, min(1800, args.timeout))
        failures = 0
        try:
            for path in args.files:
                try:
                    if args.list:
                        source = probe(path, prefs)
                        print(json.dumps({"source": str(path), "detected": source.format,
                                          "pdf_kind": source.pdf.kind if source.pdf else None,
                                          "targets": [{"format": r.target, "engine": r.engine, "warning": r.warning} for r in routes(source, prefs)]}, ensure_ascii=False))
                    else:
                        result = convert(path, args.to.lower().replace("jpeg", "jpg"), prefs)
                        print(json.dumps({"source": str(path), "outputs": [str(p) for p in result.outputs]}, ensure_ascii=False))
                except ConversionError as e:
                    print(f"{path.name}: {e}", file=sys.stderr)
                    failures += 1
        except KeyboardInterrupt:
            return 130
        return int(bool(failures))
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication
    app = QApplication([sys.argv[0]])
    app.setApplicationName("Convertix")
    app.setOrganizationName("Convertix")
    app.setDesktopFileName("org.convertix.Convertix")
    app.setWindowIcon(QIcon.fromTheme("document-export"))
    QIcon.setFallbackThemeName("breeze")
    from .gui import run_gui
    return run_gui(app, args.files)

