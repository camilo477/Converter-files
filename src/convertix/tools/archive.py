"""Creation only: safe relative member names, pinned input copies, CRC verification."""
import hashlib
import shutil
import zipfile
from pathlib import Path
from ..models import ConversionError
from ..process import run


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024*1024):
            value.update(chunk)
    return value.hexdigest()


def create(paths, params, output, progress):
    fmt = params.get("archive_format", "zip")
    level = int(params.get("compression", 6))
    if not 0 <= level <= 9 or fmt not in ("zip", "7z"):
        raise ConversionError("Formato o nivel de archivo comprimido inválido.")
    payload = output.parent/"archive-members"
    payload.mkdir(mode=0o700)
    used = set()
    for path in paths:
        name = path.name
        n = 2
        while name in used:
            name = f"{path.stem} ({n}){path.suffix}"
            n += 1
        used.add(name)
        path.rename(payload/name)
    members = sorted(payload.rglob("*"))
    expected = {p.relative_to(payload).as_posix(): digest(p) for p in members if p.is_file()}
    for path in members:
        name = path.relative_to(payload).as_posix()
        if name.startswith("/") or ".." in Path(name).parts or "\\" in name:
            raise ConversionError("Un nombre no puede representarse de forma segura dentro del archivo comprimido.")
    result = output/("archivos."+fmt)
    if fmt == "zip":
        with zipfile.ZipFile(result, "w", zipfile.ZIP_DEFLATED, compresslevel=level, strict_timestamps=False) as archive:
            for i, path in enumerate(members):
                progress(f"Comprimiendo {i+1}/{len(members)} · {path.name}")
                name = path.relative_to(payload).as_posix()
                if path.is_dir():
                    archive.mkdir(name+"/")
                else:
                    # Fixed metadata avoids exposing input filesystem times/permissions in ZIP.
                    info = zipfile.ZipInfo(name)
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = 0o100600 << 16
                    info._compresslevel = level
                    with path.open("rb") as source, archive.open(info, "w", force_zip64=True) as destination:
                        shutil.copyfileobj(source, destination, 1024*1024)
        with zipfile.ZipFile(result) as archive:
            if archive.testzip() is not None:
                raise ConversionError("La verificación CRC del ZIP falló.")
            for name, value in expected.items():
                actual = hashlib.sha256()
                with archive.open(name) as handle:
                    while chunk := handle.read(1024*1024):
                        actual.update(chunk)
                if actual.hexdigest() != value:
                    raise ConversionError("Un archivo no conserva su contenido dentro del ZIP.")
    else:
        executable = shutil.which("7z") or shutil.which("7zz")
        if not executable:
            raise ConversionError("Falta 7z; utiliza ZIP, disponible sin dependencias adicionales.")
        progress("Creando 7z y verificando su integridad…")
        run([executable, "a", "-t7z", f"-mx={level}", "-bd", str(result), "."], cwd=payload)
        run([executable, "t", "-bd", str(result)], cwd=payload)
    return {"name": "archivos."+fmt, "summary": f"Archivo {fmt.upper()} creado · {len(expected)} archivos verificados",
            "stats": {"format": fmt, "files": len(expected), "result_bytes": result.stat().st_size}}
