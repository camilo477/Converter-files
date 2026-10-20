"""Tool configuration and lazy previews; heavy work stays outside Qt's GUI thread."""
import hashlib
import shutil
import threading
from pathlib import Path
from tempfile import TemporaryDirectory
from PySide6.QtCore import QObject, Property, Signal, Slot, QUrl
from PySide6.QtWidgets import QFileDialog
from ..config import Preferences
from ..models import ConversionError
from ..notifications import notify
from .catalog import LABELS, archive_formats
from .rpc import request
from .service import batch


class ToolController(QObject):
    changed = Signal()
    previewChanged = Signal()

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.action = ""
        self.state = "closed"
        self.files = []
        self.entries = []
        self.destination = ""
        self.name = ""
        self.message = ""
        self.cancel_event = threading.Event()
        self.temporary = TemporaryDirectory(prefix="convertix-previews-")
        self.cache = {}
        self.queue = []
        self.preview_running = False
        self.revision = 0

    @Property(str, notify=changed)
    def status(self): return self.state

    @Property(str, notify=changed)
    def actionId(self): return self.action

    @Property(str, notify=changed)
    def title(self): return LABELS.get(self.action, ("Herramientas",))[0]

    @Property(str, notify=changed)
    def statusText(self): return self.message

    @Property("QVariantList", notify=changed)
    def items(self): return self.entries

    @Property(str, notify=changed)
    def outputDirectory(self): return self.destination

    @Property(str, notify=changed)
    def proposedName(self): return self.name

    @Property("QVariantList", constant=True)
    def archiveFormats(self): return archive_formats()

    @Property(int, notify=previewChanged)
    def previewVersion(self): return self.revision

    def launch(self, fn, success):
        self.owner.launch(fn, success, self.failed)

    def inspect(self):
        self.state = "loading"
        self.message = "Comprobando archivos…"
        self.changed.emit()
        paths = list(self.files)
        def work(progress):
            with TemporaryDirectory(prefix="convertix-tool-info-") as temp:
                return request(Path(temp), "__inspect__", paths, {}, self.owner.prefs, self.cancel_event)["items"]
        self.launch(work, self.inspected)

    @Slot(object)
    def inspected(self, entries):
        if self.cancel_event.is_set():
            self.state = "closed"
            self.changed.emit()
            return
        self.entries = entries
        self.state = "configure"
        self.message = ""
        if any(e.get("signed") for e in entries):
            self.message = "Hay campos de firma digital. Reescribir estos PDFs puede invalidar las firmas."
        self.changed.emit()

    def open(self, action, paths):
        if self.state in ("loading", "processing"):
            return
        self.action = action
        self.files = [Path(p).expanduser().absolute() for p in paths]
        self.entries = []
        self.destination = str(self.files[0].parent)
        stem = self.files[0].stem
        self.name = {"pdf-merge": "documentos_unidos.pdf", "pdf-split": stem+"_partes",
                     "archive": "archivos.zip", "images-pdf": "imagenes.pdf"}.get(action, "")
        self.cancel_event = threading.Event()
        self.inspect()

    @Slot(str)
    def failed(self, message):
        self.state = "closed" if self.cancel_event.is_set() else "configure"
        self.message = message
        self.changed.emit()

    @Slot(int, int)
    def move(self, source, destination):
        if self.state != "configure" or not 0 <= source < len(self.files) or not 0 <= destination < len(self.files):
            return
        self.files.insert(destination, self.files.pop(source))
        self.entries.insert(destination, self.entries.pop(source))
        self.changed.emit()

    @Slot(int)
    def remove(self, index):
        if self.state == "configure" and 0 <= index < len(self.files):
            self.files.pop(index)
            self.entries.pop(index)
            self.changed.emit()

    @Slot()
    def add(self):
        if self.state != "configure": return
        pattern = "PDF (*.pdf)" if self.action == "pdf-merge" else "Imágenes (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff *.gif)" if self.action == "images-pdf" else "Todos los archivos (*)"
        paths, _ = QFileDialog.getOpenFileNames(None, "Añadir archivos", self.destination, pattern)
        if paths:
            self.files += [Path(p) for p in paths]
            self.inspect()

    @Slot()
    def addFolder(self):
        if self.state != "configure" or self.action != "archive": return
        path = QFileDialog.getExistingDirectory(None, "Añadir carpeta", self.destination)
        if path:
            self.files.append(Path(path)); self.inspect()

    @Slot()
    def chooseDestination(self):
        if self.state != "configure": return
        folder = QFileDialog.getExistingDirectory(None, "Carpeta de destino", self.destination)
        if folder:
            self.destination = folder
            self.changed.emit()

    @Slot("QVariantMap", result=str)
    def splitPreview(self, params):
        if not self.entries or not self.entries[0].get("pages"):
            return ""
        try:
            from .pdf_ops import split_groups
            groups = split_groups(dict(params), self.entries[0]["pages"])
            counts = ", ".join(str(len(g)) for g in groups[:12])
            return f"Resultado: {len(groups)} PDF(s), con {counts}{'…' if len(groups)>12 else ''} página(s)."
        except (ConversionError, ValueError) as exc:
            return str(exc)

    @Slot(int, int, int, result=str)
    def thumbnail(self, index, page, extent):
        if not 0 <= index < len(self.files): return ""
        key = (str(self.files[index]), page, extent)
        if key in self.cache:
            return self.cache[key]
        if key not in self.queue:
            self.queue.append(key)
        self.next_preview()
        return ""

    def next_preview(self):
        if self.preview_running or not self.queue or self.state == "closed": return
        key = self.queue.pop(0)
        self.cache[key] = ""
        self.preview_running = True
        target = Path(self.temporary.name)/(hashlib.sha256(repr(key).encode()).hexdigest()+".png")
        def work(progress):
            try:
                with TemporaryDirectory(dir=self.temporary.name) as temp:
                    prefs = Preferences(timeout=30)
                    request(Path(temp), "__thumbnail__", [Path(key[0])], {"page": key[1], "extent": key[2]}, prefs, self.cancel_event)
                    shutil.copyfile(Path(temp)/"preview.png", target)
                return QUrl.fromLocalFile(str(target)).toString()
            except ConversionError:
                return ""
        def ready(url):
            self.cache[key] = url
            self.preview_running = False
            self.revision += 1
            self.previewChanged.emit()
            self.next_preview()
        self.owner.launch(work, ready, lambda message: ready(""))

    @Slot("QVariantMap")
    def execute(self, params):
        if self.state != "configure" or not self.files:
            return
        self.state = "processing"
        self.message = "Preparando operación…"
        self.cancel_event = threading.Event()
        self.changed.emit()
        params = dict(params)
        params["fingerprints"] = {str(path): entry["fingerprint"] for path, entry in zip(self.files, self.entries) if "fingerprint" in entry}
        paths, action, destination = list(self.files), self.action, self.destination
        name = str(params.pop("output_name", "")).strip() or None
        def work(progress):
            records = batch(action, paths, params, destination=destination, name=name,
                            prefs=self.owner.prefs, cancel=self.cancel_event, progress=progress)
            count = sum(r["ok"] for r in records)
            notify("Operación completada" if count == len(records) else "Operación con incidencias",
                   records[0]["detail"] if len(records) == 1 else f"{count}/{len(records)} archivos completados",
                   self.owner.prefs.notifications)
            return records
        self.launch(work, self.completed)

    @Slot(object)
    def completed(self, records):
        self.state = "closed"
        self.changed.emit()
        self.owner.completed(records)
        if all(r["ok"] for r in records):
            self.owner.message = "Operación completada"
            self.owner.changed.emit()

    @Slot()
    def cancel(self):
        self.cancel_event.set()
        self.queue.clear()
        if self.state in ("processing", "loading"):
            self.message = "Cancelando…"
        else:
            self.state = "closed"
        self.changed.emit()

    def update_progress(self, message):
        if self.state in ("loading", "processing"):
            self.message = message
            self.changed.emit()
