#!/usr/bin/env python3
"""Exercise the installed Plasma FolderModel, without changing/restarting Plasma.

Creates only uniquely named synthetic files on the actual desktop and removes them.
The menu uses Qt offscreen; --launch activates its real KIO action and checks the
separate installed radial application through AT-SPI. This is not a physical click
in the running plasmashell; that acceptance step remains manual.
"""
import argparse
import hashlib
import json
import os
import signal
import time
import uuid
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before-fix", action="store_true")
    parser.add_argument("--launch", action="store_true")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.before_fix and args.launch:
        parser.error("--launch requires the corrected integration")

    original_platform = os.environ.get("QT_QPA_PLATFORM")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["QT_LINUX_ACCESSIBILITY_ALWAYS_ON"] = "1"
    from PIL import Image
    from PySide6.QtCore import QMetaObject, QStandardPaths, QUrl
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from PySide6.QtWidgets import QApplication, QMenu
    app = QApplication([])
    if original_platform is None:
        os.environ.pop("QT_QPA_PLATFORM", None)
    else:
        os.environ["QT_QPA_PLATFORM"] = original_platform
    if args.launch:
        import pyatspi
        desktop_accessible = pyatspi.Registry.getDesktop(0)

    def wait(fn, timeout=20):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            app.processEvents()
            result = fn()
            if result:
                return result
            time.sleep(.05)
        raise RuntimeError("Timed out waiting for Folder View / Convertix")

    def processes():
        found = {}
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            try:
                argv = (entry / "cmdline").read_bytes().split(b"\0")
                if b"-m" in argv and b"convertix" in argv:
                    found[int(entry.name)] = [os.fsdecode(a) for a in argv if a]
            except (OSError, PermissionError):
                pass
        return found

    def accessible_find(node, name, depth=0):
        if depth > 25:
            return None
        try:
            if node.name == name and node.getState().contains(pyatspi.STATE_SHOWING):
                return node
            for child in node:
                found = accessible_find(child, name, depth + 1)
                if found:
                    return found
        except Exception:
            pass
        return None

    def matching_actions(menu):
        matches = []
        for action in menu.actions():
            if action.text().replace("&", "") == "Convertir…" and action.isVisible():
                matches.append(action)
            if action.menu():
                matches.extend(matching_actions(action.menu()))
        return matches

    desktop = Path(QStandardPaths.writableLocation(QStandardPaths.DesktopLocation))
    if not desktop.is_dir():
        raise RuntimeError("The configured desktop directory does not exist")
    token = "Convertix-smoke-" + uuid.uuid4().hex
    paths = [desktop / (token + suffix) for suffix in (" uno ñ.png", " dos 日本.png", " documento.pdf")]
    hashes = {}
    owned_pids = set()
    engines = []
    record = {"menu_component": "installed org.kde.private.desktopcontainment.folder/FolderModel",
              "menu_backend": app.platformName(), "session": os.environ.get("XDG_SESSION_TYPE"),
              "physical_plasmashell_click": "manual verification pending", "cases": [], "passed": False}
    try:
        for i, path in enumerate(paths):
            with path.open("xb") as stream:
                Image.new("RGB", (48 + i, 32), (30, 80 + i, 150)).save(stream, "PDF" if path.suffix == ".pdf" else "PNG")
            hashes[path] = hashlib.sha256(path.read_bytes()).hexdigest()
        for scheme, url in (("desktop", "desktop:/"), ("file", QUrl.fromLocalFile(str(desktop)).toString())):
            engine = QQmlEngine()
            engines.append(engine)
            component = QQmlComponent(engine)
            qml = ('import org.kde.private.desktopcontainment.folder as Folder\n'
                   'Folder.FolderModel { url: ' + json.dumps(url) + '; filterMode: 1; '
                   'filterPattern: ' + json.dumps(token + "*") + '; filterMimeTypes: ["all/all"] }')
            component.setData(qml.encode(), QUrl())
            model = component.create()
            if model is None:
                raise RuntimeError([e.toString() for e in component.errors()])
            wait(lambda: model.rowCount() == len(paths))
            roles = {bytes(value).decode(): key for key, value in model.roleNames().items()}
            rows = {model.data(model.index(i, 0), roles["display"]): i for i in range(model.rowCount())}
            assert all(QUrl(model.data(model.index(i, 0), roles["url"])).scheme() == scheme
                       for i in range(model.rowCount()))
            for indexes in ((0,), (0, 1), (2,), (0, 2), ()):
                selected = [paths[i] for i in indexes]
                model.clearSelection()
                for path in selected:
                    model.toggleSelected(rows[path.name])
                assert QMetaObject.invokeMethod(model, "openContextMenu")
                menu = wait(lambda: next((w for w in app.topLevelWidgets() if isinstance(w, QMenu) and w.isVisible()), None))
                actions = matching_actions(menu)
                expected = bool(selected) and not (args.before_fix and scheme == "desktop")
                case = {"scheme": scheme, "selection": [p.suffix for p in selected],
                        "action_count": len(actions), "expected_visible": expected}
                record["cases"].append(case)
                assert len(actions) == int(expected), case
                if actions:
                    assert actions[0] in menu.actions(), "Convertix must be a top-level action"
                    case["top_level"] = True
                if args.launch and selected:
                    existing = set(processes())
                    actions[0].trigger()
                    menu.close()
                    def launched():
                        for pid, argv in processes().items():
                            if pid not in existing and any(token in argument for argument in argv):
                                return pid, argv
                        return None
                    pid, argv = wait(launched)
                    owned_pids.add(pid)
                    assert "--" in argv, argv
                    received = argv[argv.index("--") + 1:]
                    assert sorted(received) == sorted(map(str, selected)), received
                    case["exact_local_argv"] = True
                    application = wait(lambda: next((a for a in desktop_accessible if a.get_process_id() == pid), None))
                    for name in ("Convertir", "Modificar"):
                        wait(lambda: accessible_find(application, name))
                    modify = accessible_find(application, "Modificar")
                    assert modify.queryAction().doAction(0)
                    wait(lambda: accessible_find(application, "Crear ZIP / 7z"))
                    case["radial_categories_and_archive_tool"] = True
                    close = wait(lambda: accessible_find(application, "Cerrar"))
                    assert close.queryAction().doAction(0)
                    wait(lambda: pid not in processes())
                    owned_pids.remove(pid)
                else:
                    menu.close()
                app.processEvents()
                print(json.dumps(case, ensure_ascii=False), flush=True)
            model.deleteLater()
            app.processEvents()
        assert all(hashlib.sha256(p.read_bytes()).hexdigest() == h for p, h in hashes.items())
        record["originals_unchanged"] = True
        record["passed"] = True
    except Exception as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        for pid in owned_pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        for path, original_hash in hashes.items():
            if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == original_hash:
                path.unlink()
        record["synthetic_files_removed"] = all(not p.exists() for p in paths)
        args.report.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
