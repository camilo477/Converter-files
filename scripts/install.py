#!/usr/bin/env python3
"""Offline per-user installation; only touches owned, hash-checked integration files."""
import argparse
import hashlib
import importlib
import importlib.metadata
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
import tomllib
import venv
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
APP_ID = "org.convertix.Convertix"
VERSION = tomllib.loads((PROJECT/"pyproject.toml").read_text())["project"]["version"]


def package_info(interpreter, name, distribution):
    code = '''import importlib,importlib.metadata,json,sys
m=importlib.import_module(sys.argv[1]);d=importlib.metadata.distribution(sys.argv[2])
entry=next((f for f in d.files or [] if f.name in ('METADATA','PKG-INFO') and any(x.endswith(('.dist-info','.egg-info')) for x in f.parts)),None)
print(json.dumps({'origin':m.__file__,'package':bool(getattr(m,'__path__',None)),'version':d.version,'metadata':str(d.locate_file(entry).parent) if entry else None}))'''
    result = subprocess.run([str(interpreter), "-I", "-c", code, name, distribution], capture_output=True, text=True)
    return json.loads(result.stdout) if result.returncode == 0 else None


def snapshot_package(info, name, site):
    origin = Path(info["origin"])
    if info["package"]:
        shutil.copytree(origin.parent, site/name, symlinks=True, ignore=shutil.ignore_patterns("__pycache__"))
    else:
        shutil.copy2(origin, site/origin.name)
    if info["metadata"]:
        metadata = Path(info["metadata"])
        if not (site/metadata.name).exists():
            shutil.copytree(metadata, site/metadata.name, symlinks=True)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def quote_exec(path):
    value = str(path).replace("%", "%%")
    for char in ("\\", '"', "`", "$"):
        value = value.replace(char, "\\" + char)
    return '"' + value.replace("\\", "\\\\") + '"'


def main():
    parser = argparse.ArgumentParser(description="Instalar Convertix sin sudo ni descargas")
    parser.add_argument("--prefix", type=Path, default=Path.home()/".local")
    args = parser.parse_args()
    prefix = args.prefix.expanduser().absolute()
    root = prefix/"share/convertix"
    created_root = not root.exists()
    manifest_path = root/"manifest.json"
    previous = {}
    if root.exists():
        if not manifest_path.exists():
            raise SystemExit(f"No se modifica un directorio ajeno sin manifiesto: {root}")
        previous = json.loads(manifest_path.read_text())
        if previous.get("app") != APP_ID:
            raise SystemExit("El manifiesto no pertenece a Convertix.")
    launcher = prefix/"bin/convertix"
    uninstaller = prefix/"bin/convertix-uninstall"
    service = prefix/"share/kio/servicemenus/convertix.desktop"
    desktop = prefix/f"share/applications/{APP_ID}.desktop"
    icon = prefix/"share/icons/hicolor/scalable/apps/convertix.svg"
    managed = [launcher, uninstaller, service, desktop, icon]
    for path in managed:
        if path.exists() or path.is_symlink():
            old_hash = previous.get("files", {}).get(str(path))
            if path.is_symlink() or not path.is_file() or digest(path) != old_hash:
                raise SystemExit(f"No se sobrescribe un archivo ajeno o modificado: {path}")
    # Check dependencies before installing anything. Snapshot Python packages offline;
    # native Qt/LibreOffice/Poppler libraries remain managed by Fedora.
    check = subprocess.run([sys.executable, "-c", "import PySide6, PIL, olefile; import ctypes.util; assert ctypes.util.find_library('seccomp')"], capture_output=True)
    if check.returncode:
        raise SystemExit("Faltan dependencias. Revisa README.md; no se ha instalado nada.")
    root.mkdir(parents=True, exist_ok=True)
    release = root/"releases"/f"{VERSION}-{time.time_ns()}"
    release.mkdir(parents=True)
    current = root/"current"
    previous_link = current.readlink() if current.is_symlink() else None
    backups = {p: (p.read_bytes(), p.stat().st_mode & 0o777) for p in managed if p.is_file()}
    written = []
    temporary_files = []
    try:
        environment = release/"venv"
        venv.EnvBuilder(with_pip=True, system_site_packages=False).create(environment)
        python = environment/"bin/python"
        site = Path(subprocess.check_output([str(python), "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"], text=True).strip())
        versions = {}
        for package in ("PySide6", "shiboken6", "PIL", "olefile"):
            distribution_name = "Pillow" if package == "PIL" else package
            info = package_info(sys.executable, package, distribution_name)
            if not info:
                raise RuntimeError(f"No se pudo preparar {package} en el entorno aislado.")
            snapshot_package(info, package, site)
            versions[distribution_name] = info["version"]
        candidates = [PROJECT/".venv/bin/python", Path(sys.executable)]
        optional = [("pymupdf", "PyMuPDF"), ("docx", "python-docx"), ("lxml", "lxml"),
                    ("typing_extensions", "typing_extensions"), ("openpyxl", "openpyxl"), ("et_xmlfile", "et-xmlfile")]
        for package, distribution_name in optional:
            info = next((info for interpreter in candidates if interpreter.exists()
                         if (info := package_info(interpreter, package, distribution_name))), None)
            if info:
                snapshot_package(info, package, site)
                versions[distribution_name] = info["version"]
        shutil.copytree(PROJECT/"src/convertix", site/"convertix", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(PROJECT/"scripts/uninstall.py", release/"uninstall.py")
        subprocess.run([str(python), "-m", "convertix", "--diagnose"], stdout=subprocess.DEVNULL, check=True)
        # Launchers point through a stable symlink, so updates do not depend on this checkout.
        if current.exists() and not current.is_symlink():
            raise RuntimeError(f"No se reemplaza un directorio ajeno: {current}")
        next_link = root/".next"
        next_link.unlink(missing_ok=True)
        next_link.symlink_to(release, target_is_directory=True)
        os.replace(next_link, current)
        exe = current/"venv/bin/python"
        launcher_text = f'#!/bin/sh\nexec {shlex.quote(str(exe))} -I -m convertix "$@"\n'
        uninstall_text = f'#!/bin/sh\nexec {shlex.quote(str(exe))} -I {shlex.quote(str(current/"uninstall.py"))} --prefix {shlex.quote(str(prefix))} "$@"\n'
        mime = "image/png;image/jpeg;image/webp;image/bmp;image/tiff;image/gif;application/pdf;text/plain;text/markdown;text/html;text/csv;text/tab-separated-values;application/rtf;application/msword;application/vnd.openxmlformats-officedocument.wordprocessingml.document;application/vnd.oasis.opendocument.text;application/vnd.ms-excel;application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;application/vnd.oasis.opendocument.spreadsheet;application/vnd.ms-powerpoint;application/vnd.openxmlformats-officedocument.presentationml.presentation;application/vnd.oasis.opendocument.presentation;"
        service_text = f'''[Desktop Entry]
Type=Service
Name=Convertix
MimeType={mime}
Actions=convertix;
X-KDE-Priority=TopLevel
X-KDE-Protocols=file

[Desktop Action convertix]
Name=Convertir…
Icon=convertix
Exec={quote_exec(launcher)} -- %F
'''
        desktop_text = f'''[Desktop Entry]
Type=Application
Name=Convertix
Comment=Convierte archivos localmente
Icon=convertix
Exec={quote_exec(launcher)} -- %F
Terminal=false
Categories=Utility;FileTools;
StartupNotify=true
'''
        content = {launcher: launcher_text.encode(), uninstaller: uninstall_text.encode(),
                   service: service_text.encode(), desktop: desktop_text.encode(), icon: (PROJECT/"assets/convertix.svg").read_bytes()}
        for path, data in content.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(path.name+".convertix-new")
            with temporary.open("xb") as f:
                temporary_files.append(temporary)
                f.write(data)
            temporary.chmod(0o755 if path in (launcher, uninstaller, service) else 0o644)
            os.replace(temporary, path)
            written.append(path)
        manifest = {"app": APP_ID, "version": VERSION, "prefix": str(prefix), "release": str(release),
                    "files": {str(p): digest(p) for p in managed}, "python": sys.version,
                    "dependencies": versions, "isolation": "venv sin system-site-packages; copia local de paquetes Python existentes"}
        next_manifest = root/".manifest-new.json"
        next_manifest.write_text(json.dumps(manifest, indent=2))
        os.replace(next_manifest, manifest_path)
    except Exception:
        for temporary in temporary_files:
            temporary.unlink(missing_ok=True)
        for path in reversed(written):
            if path in backups:
                data, mode = backups[path]
                path.write_bytes(data)
                path.chmod(mode)
            else:
                path.unlink(missing_ok=True)
        if current.is_symlink() and current.resolve() == release:
            current.unlink()
            if previous_link is not None:
                current.symlink_to(previous_link, target_is_directory=True)
        shutil.rmtree(release)
        if created_root and not manifest_path.exists():
            shutil.rmtree(root)
        raise
    if shutil.which("desktop-file-validate"):
        # Type=Service is a KDE extension; freedesktop's validator rejects its MimeType/Actions keys.
        subprocess.run(["desktop-file-validate", str(desktop)], check=True)
    import configparser
    parsed = configparser.ConfigParser(interpolation=None)
    parsed.read(service)
    assert parsed["Desktop Entry"]["Type"] == "Service" and parsed.has_section("Desktop Action convertix")
    print(f"Instalado: {launcher}\nDolphin: {service}\nDesinstalar: {uninstaller}")


if __name__ == "__main__":
    main()

