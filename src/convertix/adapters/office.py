import csv
import json
from pathlib import Path

from ..config import Preferences
from ..models import ConversionError, Source
from ..process import private_env, run
from ..registry import FILTERS, SHEETS, SLIDES


def convert(source: Source, target: str, output: Path, prefs: Preferences) -> None:
    if target == "xls":
        from ..office_limits import validate_xls_capacity
        validate_xls_capacity(source)
    if source.format == "html" and target == "odt":
        # Writer/Web otherwise emits text-web with an .odt extension. Round-trip through
        # a validated DOCX to enter ordinary Writer and produce a standard text/ODT file.
        intermediate = output.parent / "html-docx"
        intermediate.mkdir()
        convert(source, "docx", intermediate, prefs)
        from ..detect import zip_format
        bridge = intermediate / "document.docx"
        if zip_format(bridge) != "docx":
            raise ConversionError("No se pudo crear el documento intermedio desde HTML.")
        source = Source(bridge, "docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    profile = output.parent / (output.name + "-office-profile")
    user = profile / "user"
    user.mkdir(parents=True)
    # Private profile: never attach to an existing user LibreOffice, run macros or refresh links.
    (user / "registrymodifications.xcu").write_text('''<?xml version="1.0"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry">
<item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop></item>
<item oor:path="/org.openoffice.Office.Common/Load"><prop oor:name="UpdateMode" oor:op="fuse"><value>0</value></prop></item>
</oor:items>''')
    family = "calc" if source.format in SHEETS else "impress" if source.format in SLIDES else "writer"
    if target == "pdf":
        options = {"Quality": {"type": "long", "value": str(prefs.quality)},
                   "ReduceImageResolution": {"type": "boolean", "value": "false"},
                   "UseTaggedPDF": {"type": "boolean", "value": "true"}}
        if family == "calc":
            options["SinglePageSheets"] = {"type": "boolean", "value": str(prefs.sheet_pdf == "sheet").lower()}
        spec = f"pdf:{family}_pdf_Export:" + json.dumps(options, separators=(",", ":"))
    elif target in ("csv", "tsv"):
        sep = "44" if target == "csv" else "9"
        # Token 12=-1 exports ALL sheets, including hidden ones, to separate files.
        spec = f"{target}:{FILTERS[target]}:{sep},34,76,1,,0,false,true,false,false,false,-1,false"
    elif target == "txt":
        spec = "txt:Text (encoded):UTF8"
    else:
        spec = f"{target}:{FILTERS[target]}"
    args = ["libreoffice", f"-env:UserInstallation={profile.as_uri()}", "--headless", "--nologo",
            "--nodefault", "--norestore", "--nolockcheck"]
    if source.format == "md":
        args.append("--infilter=Markdown")
    elif source.format in ("csv", "tsv"):
        text = source.path.read_text(encoding="utf-8-sig")
        sep = "\t" if source.format == "tsv" else csv.Sniffer().sniff(text[:8192], delimiters=",;\t|").delimiter
        args.append(f"--infilter=Text - txt - csv (StarCalc):{ord(sep)},34,76,1,,1033,true,false,false,false,false,0,false,false,false")
    elif source.format == "txt":
        args.append("--infilter=Text (encoded):UTF8")
    args.extend(["--convert-to", spec, "--outdir", str(output), str(source.path)])
    details = run(args, cwd=output.parent, timeout=prefs.timeout, env=private_env(output.parent))
    if not any(output.iterdir()):
        raise ConversionError("LibreOffice no produjo un archivo. " + details[-3000:])

