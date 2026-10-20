"""Pinned snapshots, including directory trees without following symlinks."""
import os
import stat
import time
from pathlib import Path
from ..models import Cancelled, ConversionError

MAX_TOTAL = 2 * 1024**3
MAX_FILES = 10000


def snapshot(paths, target, cancel, timeout, progress=None, fingerprints=None):
    total = 0
    count = 0
    modes = []
    started = time.monotonic()

    def check():
        if cancel.is_set():
            raise Cancelled("Copia cancelada.")
        if time.monotonic()-started > timeout:
            raise ConversionError("La preparación superó el límite de tiempo.")

    def copy_fd(fd, destination, depth=0):
        nonlocal total, count
        check()
        if depth > 64:
            raise ConversionError("Las carpetas exceden 64 niveles; reduce la profundidad antes de comprimir.")
        before = os.fstat(fd)
        modes.append(stat.S_IMODE(before.st_mode))
        count += 1
        if count > MAX_FILES:
            raise ConversionError("La selección excede 10 000 archivos/directorios.")
        if stat.S_ISDIR(before.st_mode):
            destination.mkdir(mode=0o700)
            # Enumerate a pinned directory fd, never a symlink-resolved tree.
            for name in sorted(os.listdir(fd)):
                child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
                try:
                    copy_fd(child, destination/name, depth+1)
                finally:
                    os.close(child)
        elif stat.S_ISREG(before.st_mode):
            if before.st_size > MAX_TOTAL-total:
                raise ConversionError("La selección excede 2 GiB sin comprimir.")
            with destination.open("xb") as output:
                while chunk := os.read(fd, 1024*1024):
                    check()
                    total += len(chunk)
                    if total > MAX_TOTAL:
                        raise ConversionError("La selección creció por encima de 2 GiB.")
                    output.write(chunk)
        else:
            raise ConversionError("No se admiten enlaces simbólicos, dispositivos ni archivos especiales.")
        after = os.fstat(fd)
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ConversionError("Un original cambió durante la copia; vuelve a intentarlo.")

    copies = []
    for i, path in enumerate(paths):
        check()
        if progress:
            progress(f"Preparando {i+1}/{len(paths)} · {path.name}")
        container = target/str(i)
        container.mkdir(mode=0o700)
        destination = container/path.name
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            expected = (fingerprints or {}).get(str(path))
            st = os.fstat(fd)
            if expected and [st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns] != expected:
                raise ConversionError("Un archivo cambió desde la vista previa. Vuelve a abrir la herramienta.")
            copy_fd(fd, destination)
        finally:
            os.close(fd)
        copies.append(destination)
    return copies, modes, total
