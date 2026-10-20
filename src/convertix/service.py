"""Safe staging, cancellable process groups and atomic no-replace publication."""
import ctypes
import errno
import json
import logging
import os
import signal
import stat
import subprocess
import sys
import threading
import time
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

from .config import Preferences
from .detect import MAX_BYTES, detect
from .models import Cancelled, ConversionError, Result
from .registry import extension

log = logging.getLogger("convertix")


def rename_noreplace(source: Path, destination: Path) -> None:
    lib = ctypes.CDLL(None, use_errno=True)
    call = getattr(lib, "renameat2", None)
    if call is None:
        raise ConversionError("Este sistema no ofrece publicación atómica sin sobrescritura (renameat2).")
    call.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    call.restype = ctypes.c_int
    if call(-100, os.fsencode(source), -100, os.fsencode(destination), 1):
        error = ctypes.get_errno()
        if error in (errno.EEXIST, errno.ENOTEMPTY):
            raise FileExistsError(error, os.strerror(error), str(destination))
        raise OSError(error, os.strerror(error), str(destination))


def publish(staged: Path, parent: Path, stem: str, suffix: str, policy: str) -> Path:
    # Allow very long original basenames without exceeding NAME_MAX with the suffix.
    max_name = os.pathconf(parent, "PC_NAME_MAX")
    for number in range(1, 10001):
        extra = "" if number == 1 else f" (convertido {number})"
        base = stem
        while len(os.fsencode(base + extra + suffix)) > max_name:
            base = base[:-1]
        candidate = parent / (base + extra + suffix)
        try:
            rename_noreplace(staged, candidate)
            return candidate
        except FileExistsError:
            if policy == "fail":
                raise ConversionError("El destino ya existe. Cambia la política de nombres en Preferencias.")
    raise ConversionError("Demasiados nombres de destino ocupados.")


def stop_group(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=0.6)
    except subprocess.TimeoutExpired:
        pass
    # Reap descendants even if the group leader exited immediately on SIGTERM.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def convert(path: Path, target: str, prefs: Preferences | None = None,
            cancel: threading.Event | None = None, *, progress=None) -> Result:
    prefs = prefs or Preferences()
    cancel = cancel or threading.Event()
    if cancel.is_set():
        raise Cancelled("Conversión cancelada.")
    path = Path(os.path.abspath(path.expanduser()))
    started = time.monotonic()
    try:
        # Open without following a replaced final symlink, then copy from the pinned fd.
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as input_file:
            before = os.fstat(input_file.fileno())
            if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= MAX_BYTES:
                raise ConversionError("Archivo no regular, vacío o mayor de 512 MiB.")
            # Same-filesystem staging is necessary for atomic publication on mounted disks.
            with TemporaryDirectory(prefix=".convertix-", dir=path.parent) as temp:
                work = Path(temp)
                staged = work / "input"
                with staged.open("xb") as copied:
                    while chunk := input_file.read(1024 * 1024):
                        if cancel.is_set():
                            raise Cancelled("Conversión cancelada.")
                        if copied.tell() + len(chunk) > MAX_BYTES:
                            raise ConversionError("El archivo creció por encima de 512 MiB durante la lectura.")
                        copied.write(chunk)
                after = os.fstat(input_file.fileno())
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise ConversionError("El original cambió durante la lectura. Inténtalo de nuevo.")
                # Retain the extension only as a hint for ambiguous text formats.
                hinted = staged.with_suffix(path.suffix)
                staged.rename(hinted)
                # Heavy PDF analysis runs inside the cancellable, resource-limited worker.
                source = detect(hinted, analyze_pdf=False)
                canonical = work / f"document.{source.format}"
                hinted.rename(canonical)
                output = work / "output"
                output.mkdir(mode=0o700)
                request = work / "request.json"
                request.write_text(json.dumps({"source": str(canonical), "target": target,
                                              "output": str(output), "prefs": asdict(prefs)}))
                env = os.environ.copy()
                # Absolute package path works from any launcher working directory.
                env.pop("PYTHONPATH", None)
                entrypoint = Path(__file__).resolve().parent / "worker_entry.py"
                process = subprocess.Popen([sys.executable, "-I", str(entrypoint), str(request)],
                                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE, env=env, start_new_session=True)
                last_progress = ""
                try:
                    while True:
                        if cancel.is_set():
                            raise Cancelled("Conversión cancelada; el original permanece intacto.")
                        if time.monotonic() - started > prefs.timeout:
                            raise ConversionError(f"La conversión superó {prefs.timeout} segundos. Puedes ampliar el límite con --timeout.")
                        if progress:
                            try:
                                message = (work/"progress.txt").read_text()
                                if message and message != last_progress:
                                    progress(message)
                                    last_progress = message
                            except OSError:
                                pass
                        try:
                            stdout, stderr = process.communicate(timeout=0.1)
                            break
                        except subprocess.TimeoutExpired:
                            continue
                finally:
                    stop_group(process)
                response = work / "result.json"
                if not response.exists():
                    raise ConversionError("El motor se cerró inesperadamente. " + stderr.decode(errors="replace")[-2000:])
                data = json.loads(response.read_text())
                if not data.get("ok"):
                    log.error("worker_failed %s", json.dumps({"target": target, "detail": data.get("detail", "")}, ensure_ascii=False))
                    raise ConversionError(data.get("error", "No se pudo convertir el archivo."))
                if cancel.is_set():
                    raise Cancelled("Conversión cancelada.")
                files = sorted(p for p in output.rglob("*") if p.is_file())
                if not files:
                    raise ConversionError("No hay resultados para publicar.")
                for p in files:
                    # Conversion must not make a private input readable to more users.
                    p.chmod(stat.S_IMODE(before.st_mode) & 0o644)
                    with p.open("rb") as f:
                        os.fsync(f.fileno())
                if len(files) == 1:
                    destination = publish(files[0], path.parent, path.stem, "." + extension(target), prefs.conflicts)
                    result = Result(path, target, [destination], destination)
                else:
                    # Publish the whole set with ONE atomic rename. Sidecar references stay intact.
                    destination = publish(output, path.parent, path.stem, f" ({target.upper()})", prefs.conflicts)
                    result = Result(path, target, [destination / p.relative_to(output) for p in files], destination)
                directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    try:
                        os.fsync(directory_fd)
                    except OSError:
                        pass  # Some external filesystems do not implement directory fsync.
                finally:
                    os.close(directory_fd)
                log.info("conversion_finished %s", json.dumps({"target": target, "outputs": len(result.outputs),
                                                               "seconds": round(time.monotonic() - started, 2)}))
                return result
    except ConversionError:
        raise
    except (OSError, ValueError) as e:
        raise ConversionError(f"No se pudo leer el archivo o guardar el resultado: {e}") from e

