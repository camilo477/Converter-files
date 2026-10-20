import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile


@dataclass
class Preferences:
    theme: str = "system"
    animations: bool = True
    notifications: bool = True
    conflicts: str = "rename"
    quality: int = 92
    pdf_dpi: int = 150
    sheet_pdf: str = "print"
    timeout: int = 180
    radial_transparency: int = 85
    ocr_languages: str = "spa+eng"

    @classmethod
    def from_dict(cls, data: dict) -> "Preferences":
        p = cls()
        for key, allowed in {"theme": ("system", "light", "dark"),
                             "conflicts": ("rename", "fail"),
                             "sheet_pdf": ("print", "sheet")}.items():
            if data.get(key) in allowed:
                setattr(p, key, data[key])
        for key in ("animations", "notifications"):
            if isinstance(data.get(key), bool):
                setattr(p, key, data[key])
        for key, low, high in (("quality", 30, 100), ("pdf_dpi", 72, 300), ("timeout", 10, 1800),
                               ("radial_transparency", 0, 100)):
            if type(data.get(key)) is int:
                setattr(p, key, max(low, min(high, data[key])))
        languages = data.get("ocr_languages")
        if isinstance(languages, str) and re.fullmatch(r"[A-Za-z0-9_]+(?:\+[A-Za-z0-9_]+)*", languages) and len(languages) <= 100:
            p.ocr_languages = "+".join(dict.fromkeys(languages.split("+")))
        return p


def config_path() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "convertix/preferences.json"


def load() -> Preferences:
    try:
        data = json.loads(config_path().read_text())
        return Preferences.from_dict(data if isinstance(data, dict) else {})
    except (OSError, ValueError):
        return Preferences()


def save(p: Preferences) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = None
    try:
        try:
            previous = json.loads(path.read_text())
            if not isinstance(previous, dict):
                previous = {}
        except (OSError, ValueError):
            previous = {}
        previous.update(asdict(p))
        with NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as f:
            temporary = Path(f.name)
            json.dump(previous, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)

