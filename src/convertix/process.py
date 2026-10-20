"""Argument-only subprocesses; their process group is owned by service.py."""
import os
import subprocess
from pathlib import Path
from tempfile import TemporaryFile

from .models import ConversionError


def run(args: list[str], *, cwd: Path | None = None, timeout: int = 180,
        env: dict | None = None) -> str:
    with TemporaryFile() as capture:
        try:
            p = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=capture,
                               stderr=subprocess.STDOUT, cwd=cwd, env=env,
                               timeout=timeout, check=False)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise ConversionError(f"No se pudo completar el motor: {e}") from e
        capture.seek(0)
        output = capture.read(32000).decode("utf-8", errors="replace")
        if p.returncode:
            raise ConversionError(f"El motor terminó con código {p.returncode}. {output[-4000:]}")
        return output


def private_env(home: Path) -> dict[str, str]:
    runtime = home / "runtime"
    runtime.mkdir(mode=0o700, exist_ok=True)
    env = os.environ.copy()
    env.update(HOME=str(home), XDG_CONFIG_HOME=str(home / "config"),
               XDG_CACHE_HOME=str(home / "cache"), XDG_DATA_HOME=str(home / "data"),
               XDG_RUNTIME_DIR=str(runtime), SAL_USE_VCLPLUGIN="svp", GSETTINGS_BACKEND="memory")
    for key in ("DBUS_SESSION_BUS_ADDRESS", "DISPLAY", "WAYLAND_DISPLAY", "SESSION_MANAGER"):
        env.pop(key, None)
    return env

