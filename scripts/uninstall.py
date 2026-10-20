#!/usr/bin/env python3
import argparse
import hashlib
import json
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Eliminar únicamente la instalación de Convertix")
    parser.add_argument("--prefix", type=Path, default=Path.home()/".local")
    parser.add_argument("--purge", action="store_true", help="Eliminar también preferencias y registros personales")
    args = parser.parse_args()
    root = args.prefix.expanduser().absolute()/"share/convertix"
    manifest_path = root/"manifest.json"
    if not manifest_path.exists():
        raise SystemExit("No existe una instalación administrada de Convertix.")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("app") != "org.convertix.Convertix" or manifest.get("prefix") != str(args.prefix.expanduser().absolute()):
        raise SystemExit("Manifiesto no válido. No se ha eliminado nada.")
    for name, expected in manifest["files"].items():
        path = Path(name)
        if not path.is_relative_to(args.prefix.expanduser().absolute()):
            raise SystemExit("Ruta ajena al prefijo en el manifiesto.")
        if path.is_symlink():
            print(f"Se conserva un enlace modificado: {path}")
        elif path.is_file():
            if hashlib.sha256(path.read_bytes()).hexdigest() == expected:
                path.unlink()
            else:
                print(f"Se conserva un archivo modificado: {path}")
    shutil.rmtree(root)
    if args.purge:
        import os
        for base, suffix in ((Path(os.environ.get("XDG_CONFIG_HOME", Path.home()/".config")), "convertix"),
                             (Path(os.environ.get("XDG_STATE_HOME", Path.home()/".local/state")), "convertix")):
            folder = base/suffix
            if folder.is_dir() and not folder.is_symlink():
                shutil.rmtree(folder)
    print("Convertix desinstalado. Los documentos y este repositorio se conservan.")


if __name__ == "__main__":
    main()
