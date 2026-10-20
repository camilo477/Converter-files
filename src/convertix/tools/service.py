"""Editing orchestration: snapshots → worker → validation → atomic publication."""
import os
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from ..config import Preferences
from ..models import ConversionError, Cancelled
from ..detect import MAX_BYTES
from ..service import publish
from .rpc import request
from .staging import snapshot


@dataclass
class ToolResult:
    location: Path
    outputs: list[Path]
    summary: str
    stats: dict = field(default_factory=dict)


def safe_name(name):
    if not isinstance(name, str) or not name.strip() or name in (".", "..") or any(c in name for c in '/\\\x00\r\n'):
        raise ConversionError("Introduce un nombre de archivo sin carpetas ni caracteres de control.")
    if any(ord(c) < 32 for c in name):
        raise ConversionError("El nombre contiene caracteres de control.")
    return name.strip()


def perform(action, paths, params=None, *, destination=None, name=None, prefs=None, cancel=None, progress=None):
    prefs = prefs or Preferences()
    cancel = cancel or threading.Event()
    params = dict(params or {})
    from .options import validate
    validate(params)
    paths = [Path(os.path.abspath(Path(p).expanduser())) for p in paths]
    if not paths:
        raise ConversionError("Selecciona al menos un archivo.")
    for path in paths:
        fingerprint = params.get("fingerprints", {}).get(str(path))
        if fingerprint:
            try:
                st = path.stat()
                if [st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns] != fingerprint:
                    raise ConversionError("Un archivo cambió desde la vista previa. Vuelve a abrir la herramienta.")
            except OSError as exc:
                raise ConversionError(f"No se pudo volver a comprobar la selección: {exc}") from exc
    if action != "archive":
        try:
            if any(not p.is_file() or p.is_symlink() or p.stat().st_size > MAX_BYTES for p in paths):
                raise ConversionError("Selecciona archivos regulares de hasta 512 MiB, sin enlaces simbólicos.")
        except OSError as exc:
            raise ConversionError(f"No se pudo acceder a la selección: {exc}") from exc
    parent = Path(destination).expanduser().absolute() if destination else paths[0].parent
    if action == "archive":
        for source in paths:
            if source.is_dir() and parent.resolve().is_relative_to(source.resolve()):
                raise ConversionError("Guarda el archivo comprimido fuera de las carpetas seleccionadas.")
    try:
        with TemporaryDirectory(prefix=".convertix-", dir=parent) as temporary:
            work = Path(temporary)
            inputs = work/"inputs"
            inputs.mkdir(mode=0o700)
            copies, modes, total = snapshot(paths, inputs, cancel, prefs.timeout, progress, params.get("fingerprints"))
            params["original_names"] = [p.name for p in paths]
            response = request(work, action, copies, params, prefs, cancel, progress)
            output = work/"output"
            files = sorted(output.rglob("*"))
            if any(p.is_symlink() for p in files):
                raise ConversionError("El motor generó un enlace simbólico inesperado.")
            files = [p for p in files if p.is_file()]
            if not files:
                raise ConversionError("La herramienta no generó archivos válidos.")
            mode = 0o644
            for value in modes:
                mode &= value
            for path in files:
                path.chmod(mode)
                with path.open("rb") as handle:
                    os.fsync(handle.fileno())
            if cancel.is_set():
                raise Cancelled("Operación cancelada.")
            suggested = safe_name(name or response["name"])
            is_set = len(files) > 1 or response.get("directory", False)
            suffix = "" if is_set else files[0].suffix
            stem = suggested if is_set else (suggested[:-len(suffix)] if suffix and suggested.lower().endswith(suffix) else suggested)
            location = publish(output if is_set else files[0], parent, stem, suffix, prefs.conflicts)
            directory_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                try:
                    os.fsync(directory_fd)
                except OSError:
                    pass
            finally:
                os.close(directory_fd)
            logging.getLogger("convertix").info("tool_finished action=%s outputs=%s", action, len(files))
            return ToolResult(location, [location/p.relative_to(output) for p in files] if is_set else [location],
                              response["summary"], response.get("stats", {}))
    except ConversionError:
        raise
    except (OSError, ValueError) as exc:
        raise ConversionError(f"No se pudo preparar o publicar el resultado: {exc}") from exc


def batch(action, paths, params=None, *, prefs=None, cancel=None, progress=None, **kwargs):
    """Independent batch outputs stay explicit; split sets publish as a single folder."""
    cancel = cancel or threading.Event()
    groups = [paths] if action in ("pdf-merge", "images-pdf", "archive", "pdf-split", "crop") else [[p] for p in paths]
    records = []
    for index, group in enumerate(groups):
        label = Path(group[0]).name if len(group) == 1 else f"{len(group)} archivos"
        try:
            if cancel.is_set():
                raise Cancelled("Pendiente cancelado.")
            prefix = f"{index+1}/{len(groups)}"
            result = perform(action, group, params, prefs=prefs, cancel=cancel,
                             progress=(lambda m: progress(prefix+" · "+m)) if progress else None, **kwargs)
            records.append({"name": label, "ok": True, "location": str(result.location), "detail": result.summary,
                            "stats": result.stats, "outputs": len(result.outputs)})
        except ConversionError as exc:
            logging.getLogger("convertix").warning("tool_failed action=%s error=%s", action, exc)
            records.append({"name": label, "ok": False, "location": "", "detail": str(exc)})
    return records
