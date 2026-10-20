"""Bounded cancellable requests to the existing disposable worker."""
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path
from ..models import Cancelled, ConversionError
from ..service import stop_group


def request(folder, action, sources, params, prefs, cancel, progress=None):
    folder = Path(folder)
    payload = {"action": action, "sources": [str(p) for p in sources], "params": params,
               "prefs": asdict(prefs)}
    path = folder/"request.json"
    path.write_text(json.dumps(payload))
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    entry = Path(__file__).resolve().parents[1]/"worker_entry.py"
    process = subprocess.Popen([sys.executable, "-I", str(entry), str(path)], env=env,
                               stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=True)
    deadline = time.monotonic()+prefs.timeout
    previous = ""
    try:
        while True:
            if cancel.is_set():
                raise Cancelled("Operación cancelada; los originales permanecen intactos.")
            if time.monotonic() > deadline:
                raise ConversionError("La herramienta superó el límite de tiempo configurado.")
            if progress:
                try:
                    message = (folder/"progress.txt").read_text()
                    if message and message != previous:
                        previous = message
                        progress(message)
                except OSError:
                    pass
            try:
                _, stderr = process.communicate(timeout=0.1)
                break
            except subprocess.TimeoutExpired:
                continue
    finally:
        stop_group(process)
    try:
        response = json.loads((folder/"result.json").read_text())
    except (OSError, ValueError) as exc:
        raise ConversionError("El motor no completó la operación. "+stderr.decode(errors="replace")[-1500:]) from exc
    if not response.get("ok"):
        raise ConversionError(response.get("error", "La herramienta falló."))
    if cancel.is_set():
        raise Cancelled("Operación cancelada.")
    return response
