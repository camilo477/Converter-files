"""Cancellable, resource-limited inspection for desktop and CLI availability checks."""
import json
import os
import subprocess
import sys
import threading
import time
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

from .config import Preferences
from .models import Cancelled, ConversionError, PdfPageInfo, PdfProfile, Source
from .service import stop_group


def probe(path: Path, prefs: Preferences | None = None, cancel: threading.Event | None = None) -> Source:
    prefs = prefs or Preferences()
    cancel = cancel or threading.Event()
    with TemporaryDirectory(prefix="convertix-probe-") as temporary:
        folder = Path(temporary)
        request = folder/"request.json"
        request.write_text(json.dumps({"source": str(path.expanduser().absolute()), "target": "__probe__", "prefs": asdict(prefs)}))
        env = os.environ.copy(); env.pop("PYTHONPATH", None)
        entrypoint = Path(__file__).resolve().parent/"worker_entry.py"
        process = subprocess.Popen([sys.executable, "-I", str(entrypoint), str(request)],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   env=env, start_new_session=True)
        deadline = time.monotonic()+min(prefs.timeout, 60)
        try:
            while True:
                if cancel.is_set():
                    raise Cancelled("Comprobación cancelada.")
                if time.monotonic() > deadline:
                    raise ConversionError("El análisis del archivo superó el límite de tiempo.")
                try:
                    _, stderr = process.communicate(timeout=0.1)
                    break
                except subprocess.TimeoutExpired:
                    continue
        finally:
            stop_group(process)
        response = folder/"result.json"
        if not response.exists():
            raise ConversionError("El analizador no pudo validar el archivo. "+stderr.decode(errors="replace")[-1500:])
        result = json.loads(response.read_text())
        if not result.get("ok"):
            raise ConversionError(result.get("error", "No se pudo analizar el archivo."))
        data = result["source"]
        profile = data.get("pdf")
        if profile:
            profile = PdfProfile(profile["kind"], tuple(PdfPageInfo(**page) for page in profile["pages"]))
        return Source(Path(data["path"]), data["format"], data["mime"], data["frames"], data["has_text"], tuple(data["warnings"]), profile)
