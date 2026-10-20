import logging
import threading
from dataclasses import asdict
from pathlib import Path

from PySide6.QtCore import QObject, Property, QThread, QUrl, Signal, Slot, QSize, QStandardPaths, QSettings
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickImageProvider, QQuickWindow
from PySide6.QtWidgets import QFileDialog

from . import config
from .detect import detect
from .models import Cancelled, ConversionError
from .notifications import notify
from .registry import common_routes, diagnostics
from .service import convert
from .probe import probe

ICON = {"pdf": "application-pdf", "docx": "x-office-document", "odt": "x-office-document",
        "rtf": "x-office-document", "txt": "text-plain", "md": "text-markdown", "html": "text-html",
        "xlsx": "x-office-spreadsheet", "ods": "x-office-spreadsheet", "csv": "text-csv", "tsv": "text-csv",
        "pptx": "x-office-presentation", "odp": "x-office-presentation"}
ICON["pdf-ocr"] = "application-pdf"
FORMAT_NAMES = {"docx": "Microsoft Word", "xlsx": "Microsoft Excel", "md": "Markdown",
                "html": "Página web HTML", "pdf-ocr": "PDF con texto seleccionable",
                "odt": "OpenDocument", "rtf": "Texto enriquecido", "txt": "Texto sin formato"}
COLORS = {"pdf": "#e56870", "docx": "#619fea", "odt": "#619fea", "xlsx": "#57b993", "ods": "#57b993",
          "csv": "#57b993", "tsv": "#57b993", "pptx": "#eaa565", "odp": "#eaa565", "md": "#b18ae4"}


class Icons(QQuickImageProvider):
    def __init__(self):
        super().__init__(QQuickImageProvider.Pixmap)

    def requestPixmap(self, identifier, size, requestedSize):
        extent = requestedSize if requestedSize.isValid() else QSize(48, 48)
        icon = QIcon.fromTheme(identifier, QIcon.fromTheme("text-x-generic"))
        if icon.isNull():
            from PySide6.QtWidgets import QApplication, QStyle
            icon = QApplication.style().standardIcon(QStyle.SP_FileIcon)
        pixmap = icon.pixmap(extent)
        size.setWidth(pixmap.width())
        size.setHeight(pixmap.height())
        return pixmap


class Job(QThread):
    ready = Signal(object)
    failed = Signal(str)
    progress = Signal(str)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self.fn = fn

    def run(self):
        try:
            self.ready.emit(self.fn(self.progress.emit))
        except Exception as e:
            logging.getLogger("convertix").exception("job_failed")
            self.failed.emit(str(e))


class Controller(QObject):
    changed = Signal()
    preferencesChanged = Signal()

    def __init__(self, files: list[Path], parent=None):
        super().__init__(parent)
        self.files = files
        self.sources = []
        self.options = []
        self.records = []
        self.state = "empty"
        self.message = "Selecciona archivos para convertir"
        self.details = ""
        self.prefs = config.load()
        kde = QSettings(str(Path.home()/".config/kdeglobals"), QSettings.IniFormat)
        try:
            if float(kde.value("KDE/AnimationDurationFactor", 1)) <= 0:
                self.prefs.animations = False
        except (TypeError, ValueError):
            pass
        self.cancel_event = threading.Event()
        self.job = None
        self._jobs = []

    @Property(str, notify=changed)
    def status(self):
        return self.state

    @Property(str, notify=changed)
    def statusText(self):
        return self.message

    @Property(str, notify=changed)
    def technicalDetails(self):
        return self.details

    @Property("QVariantList", notify=changed)
    def targets(self):
        return self.options

    @Property("QVariantList", notify=changed)
    def results(self):
        return self.records

    @Property(str, notify=changed)
    def sourceName(self):
        return self.files[0].name if len(self.files) == 1 else f"{len(self.files)} archivos"

    @Property(str, notify=changed)
    def sourceFormat(self):
        fmts = {s.format.upper() for s in self.sources}
        return next(iter(fmts)) if len(fmts) == 1 else "LOTE" if fmts else "ARCHIVO"

    @Property(str, notify=changed)
    def sourceIcon(self):
        return ICON.get(self.sources[0].format, "image-x-generic") if self.sources else "document-open"

    @Property("QVariantMap", notify=preferencesChanged)
    def preferences(self):
        return asdict(self.prefs)

    def launch(self, fn, success):
        job = Job(fn, self)
        self.job = job
        self._jobs.append(job)
        job.ready.connect(success)
        job.failed.connect(self.fail)
        job.progress.connect(self.progress)
        job.finished.connect(lambda: self._cleanup(job))
        job.start()

    def _cleanup(self, job):
        self._jobs.remove(job)
        if self.job is job:
            self.job = None
        job.deleteLater()

    @Slot()
    def scan(self):
        if not self.files:
            return
        self.cancel_event = threading.Event()
        self.state = "scanning"
        self.message = "Comprobando contenido y motores…"
        self.records = []
        self.details = ""
        self.changed.emit()
        def work(progress):
            sources = []
            for i, path in enumerate(self.files, 1):
                if self.cancel_event.is_set():
                    raise Cancelled("Comprobación cancelada.")
                progress(f"Comprobando {i}/{len(self.files)} · {path.name}")
                sources.append(probe(path, self.prefs, self.cancel_event))
            return sources, common_routes(sources, self.prefs)
        self.launch(work, self.scanned)

    @Slot(object)
    def scanned(self, payload):
        self.sources, choices = payload
        notes = list(dict.fromkeys(w for s in self.sources for w in s.warnings))
        self.options = [{"target": r.target, "label": "PDF + OCR" if r.target == "pdf-ocr" else r.target.upper(), "icon": ICON.get(r.target, "image-x-generic"),
                         "accent": COLORS.get(r.target, "#aa98d7"), "hint": " ".join([FORMAT_NAMES.get(r.target, r.target.upper()), r.description, r.warning] + notes)}
                        for r in choices]
        self.state = "ready" if choices else "unavailable"
        self.message = "Elige el formato de destino" if choices else "No hay conversiones disponibles para toda la selección."
        self.changed.emit()

    @Slot(str)
    def progress(self, message):
        self.message = message
        self.changed.emit()

    @Slot(str)
    def start(self, target):
        if self.state != "ready" or target not in {o["target"] for o in self.options}:
            return
        self.state = "processing"
        self.message = f"Preparando {target.upper()}…"
        self.cancel_event = threading.Event()
        self.changed.emit()
        files = list(self.files)
        prefs = config.Preferences.from_dict(asdict(self.prefs))
        def work(progress):
            records = []
            for i, path in enumerate(files, 1):
                if self.cancel_event.is_set():
                    records.extend({"name": p.name, "ok": False, "detail": "Pendiente cancelado", "location": ""} for p in files[i-1:])
                    break
                progress(f"Convirtiendo {i}/{len(files)} · {path.name}")
                try:
                    result = convert(path, target, prefs, self.cancel_event,
                                     progress=lambda message: progress(f"{i}/{len(files)} · {message}"))
                    records.append({"name": path.name, "ok": True, "detail": f"{target.upper()} · {result.location.name}",
                                    "location": str(result.location)})
                except ConversionError as e:
                    records.append({"name": path.name, "ok": False, "detail": str(e), "location": ""})
            successes = sum(r["ok"] for r in records)
            if successes == len(files):
                notify("Archivo convertido correctamente" if len(files) == 1 else "Archivos convertidos correctamente",
                       records[0]["detail"] if len(files) == 1 else f"{successes} archivos · {target.upper()}", prefs.notifications)
            else:
                notify("Conversión finalizada con incidencias", f"{successes} correctos · {len(files)-successes} errores o cancelados", prefs.notifications)
            return records
        self.launch(work, self.completed)

    @Slot(object)
    def completed(self, records):
        self.records = records
        successes = sum(r["ok"] for r in records)
        self.state = "done" if successes == len(records) else "error"
        self.message = "Conversión completada" if self.state == "done" else f"{successes} correctos · {len(records)-successes} con incidencias"
        self.details = "\n\n".join(f"{r['name']}\n{r['detail']}" for r in records)
        self.changed.emit()

    @Slot(str)
    def fail(self, detail):
        self.state = "error"
        self.message = "No se pudo completar la operación"
        self.details = detail
        self.changed.emit()

    @Slot()
    def cancel(self):
        self.cancel_event.set()
        self.message = "Cancelando; se conservan los resultados ya completados…"
        self.changed.emit()

    @Slot(result=bool)
    def mayClose(self):
        if any(j.isRunning() for j in self._jobs):
            self.cancel()
            return False
        return True

    @Slot()
    def chooseFiles(self):
        if self.state in ("processing", "scanning"):
            return
        paths, _ = QFileDialog.getOpenFileNames(None, "Archivos para convertir")
        if paths:
            self.files = [Path(p) for p in paths]
            self.scan()

    @Slot(str, bool)
    def openResult(self, location, reveal):
        if not location or not any(r["location"] == location and r["ok"] for r in self.records):
            return
        if reveal:
            from PySide6.QtCore import QProcess
            # Dolphin's --select supports files and directories and does not use a shell.
            QProcess.startDetached("dolphin", ["--select", location])
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(location))

    @Slot("QVariantMap")
    def savePreferences(self, data):
        try:
            prefs = config.Preferences.from_dict(asdict(self.prefs) | data)
            config.save(prefs)
            self.prefs = prefs
            self.preferencesChanged.emit()
            if self.state == "ready":
                self.scanned((self.sources, common_routes(self.sources, prefs)))
        except OSError as e:
            self.fail(f"No se pudieron guardar las preferencias: {e}")

    @Slot(result=str)
    def dependencyInfo(self):
        import json
        return json.dumps(diagnostics(), ensure_ascii=False, indent=2)


def create_engine(controller: Controller):
    QQuickWindow.setDefaultAlphaBuffer(True)
    locations = QStandardPaths.standardLocations(QStandardPaths.GenericDataLocation)
    QIcon.setThemeSearchPaths(list(dict.fromkeys(QIcon.themeSearchPaths() + [str(Path(p)/"icons") for p in locations])))
    if not QIcon.themeName():
        kde = QSettings(str(Path.home()/".config/kdeglobals"), QSettings.IniFormat)
        QIcon.setThemeName(str(kde.value("Icons/Theme", "breeze")))
    QIcon.setFallbackThemeName("breeze")
    engine = QQmlApplicationEngine()
    engine.addImageProvider("theme", Icons())
    engine.rootContext().setContextProperty("backend", controller)
    engine.load(QUrl.fromLocalFile(str(Path(__file__).parent / "qml/Main.qml")))
    return engine


def run_gui(app, files: list[Path]) -> int:
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QCursor, QGuiApplication
    controller = Controller(files)
    engine = create_engine(controller)
    if not engine.rootObjects():
        return 1
    window = engine.rootObjects()[0]
    screen = QGuiApplication.screenAt(QCursor.pos()) or app.primaryScreen()
    if screen:
        area = screen.availableGeometry()
        scale = min(1.0, (area.width()-24)/640, (area.height()-24)/664)
        window.setProperty("uiScale", max(0.35, scale))
        window.setScreen(screen)
        if app.platformName() == "xcb":
            cursor = QCursor.pos()
            window.setPosition(max(area.left(), min(cursor.x()-window.width()//2, area.right()-window.width())),
                               max(area.top(), min(cursor.y()-window.height()//2, area.bottom()-window.height())))
        # On Wayland the compositor places the top-level window. No fake cursor positioning.
    window.show()
    QTimer.singleShot(0, controller.scan)
    return app.exec()

