import hashlib
import os
import shutil
import signal
import subprocess
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from PIL import Image

from convertix.config import Preferences
from convertix.detect import detect
from convertix.models import Cancelled, ConversionError
from convertix.process import run
from convertix.registry import common_routes, routes
from convertix.service import convert


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.integration
@pytest.mark.parametrize("origin,target", [("docx", "pdf"), ("odt", "docx"), ("xlsx", "pdf"),
    ("csv", "xlsx"), ("pptx", "pdf"), ("md", "docx"), ("png", "jpg"), ("jpg", "pdf"), ("pdf", "png")])
def test_required_conversions(origin, target, samples, tmp_path):
    if origin not in samples:
        pytest.skip(f"Motor de origen {origin} no instalado")
    source = tmp_path/f"prueba con espacios café 日本.{origin}"
    shutil.copyfile(samples[origin], source)
    if target not in {r.target for r in routes(detect(source))}:
        pytest.skip(f"Dependencias ausentes para {origin} → {target}")
    before = sha(source)
    result = convert(source, target)
    assert sha(source) == before
    assert result.outputs and all(p.is_file() and p.stat().st_size > 0 for p in result.outputs)
    for output in result.outputs:
        assert detect(output).format == target
    if target == "pdf" and origin in ("docx", "xlsx", "pptx"):
        text = run(["pdftotext", str(result.outputs[0]), "-"])
        assert "Convertix" in text and "123" in text
    if target == "docx":
        with zipfile.ZipFile(result.outputs[0]) as z:
            text = z.read("word/document.xml").decode()
            assert "Convertix" in text and "café" in text and "123" in text
    if origin == "csv":
        with zipfile.ZipFile(result.outputs[0]) as z:
            text = ''.join(z.read(n).decode() for n in z.namelist() if n.startswith("xl/") and n.endswith(".xml"))
            assert "42" in text and "café" in text and "=2+2" in text
            assert "<f>" not in text  # CSV formulas are imported as text.


@pytest.mark.integration
@pytest.mark.parametrize("origin", ["docx", "odt", "rtf", "txt", "html", "md", "xlsx", "ods", "csv", "tsv", "pptx", "odp", "png", "jpg", "webp", "bmp", "tiff", "gif", "pdf"])
def test_every_advertised_route(origin, samples, tmp_path):
    if origin not in samples:
        pytest.skip(f"No hay motor para crear la muestra {origin}")
    source = tmp_path/f"muestra.{origin}"
    shutil.copyfile(samples[origin], source)
    before = sha(source)
    choices = routes(detect(source))
    if not choices:
        pytest.skip(f"No hay destinos instalados para {origin}")
    for route in choices:
        result = convert(source, route.target)
        assert result.outputs and all(p.stat().st_size > 0 for p in result.outputs), route
    assert sha(source) == before
    assert not list(tmp_path.glob(".convertix-*"))


def test_conflict_unicode_wrong_extension_and_concurrency(tmp_path):
    original = tmp_path/'foto con tildes ñ $ ` 日本.txt'
    Image.new("RGBA", (90, 60), (255, 0, 0, 64)).save(original, "PNG")
    assert detect(original).format == "png"
    first = original.with_suffix(".jpg"); first.write_bytes(b"NO TOCAR")
    before = sha(original)
    with ThreadPoolExecutor(max_workers=3) as pool:
        outputs = list(pool.map(lambda _: convert(original, "jpg").outputs[0], range(3)))
    assert len(set(outputs)) == 3
    assert first.read_bytes() == b"NO TOCAR" and sha(original) == before
    for output in outputs:
        with Image.open(output) as im:
            assert im.mode == "RGB" and im.size == (90, 60)
            assert im.getpixel((5,5))[1] > 180  # Red alpha was composed onto white.
    with pytest.raises(ConversionError, match="ya existe"):
        convert(original, "jpg", Preferences(conflicts="fail"))


@pytest.mark.parametrize("content,suffix", [(b"PKbad", "docx"), (b"%PDF-bad", "pdf"),
    (b"This is not an Office file", "docx"), (b"\x00\xffbad", "bin"), (b"", "png")])
def test_corrupt_unsupported(tmp_path, content, suffix):
    p=tmp_path/f"roto.{suffix}"; p.write_bytes(content)
    with pytest.raises(ConversionError):
        detect(p)


def test_symlink_and_readonly(tmp_path):
    p=tmp_path/"original.png"; Image.new("RGB", (10, 10)).save(p)
    link=tmp_path/"enlace.png"; link.symlink_to(p)
    with pytest.raises(ConversionError):
        detect(link)
    with pytest.raises(ConversionError):
        convert(link, "jpg")
    folder=tmp_path/"sin escritura"; folder.mkdir(); q=folder/p.name; shutil.copyfile(p,q)
    folder.chmod(0o500)
    try:
        if os.geteuid() == 0:
            pytest.skip("root ignora permisos POSIX; ejecutar como usuario normal")
        with pytest.raises(ConversionError):
            convert(q, "jpg")
    finally:
        folder.chmod(0o700)


def test_real_cancellation_and_cleanup(tmp_path, monkeypatch):
    import convertix.service as service
    p=tmp_path/"grande.png"; Image.new("RGB", (4000,4000), "navy").save(p)
    before=sha(p); cancel=threading.Event(); processes=[]
    original_popen=service.subprocess.Popen
    def intercept(*args, **kwargs):
        proc=original_popen(*args,**kwargs)
        if kwargs.get("start_new_session"):
            processes.append(proc)
            threading.Timer(0.05, cancel.set).start()
        return proc
    monkeypatch.setattr(service.subprocess,"Popen",intercept)
    with pytest.raises(Cancelled):
        service.convert(p,"pdf",cancel=cancel)
    assert processes and all(proc.poll() is not None for proc in processes)
    assert sha(p)==before
    assert not list(tmp_path.glob(".convertix-*")) and not list(tmp_path.glob("*.pdf"))


def test_timeout_no_publication(tmp_path):
    p=tmp_path/"timeout.png"; Image.new("RGB", (100,100)).save(p)
    with pytest.raises(ConversionError,match="superó"):
        convert(p,"pdf",Preferences(timeout=0))
    assert not list(tmp_path.glob("*.pdf")) and not list(tmp_path.glob(".convertix-*"))


def test_animation_and_multiframe_pdf(tmp_path):
    p=tmp_path/"animación.gif"
    Image.new("RGB", (64,64),"red").save(p,save_all=True,append_images=[Image.new("RGB",(64,64),"blue")],duration=[80,140],loop=0)
    assert detect(p).frames==2
    for target in ("jpg","png","webp","bmp","tiff","pdf"):
        result=convert(p,target)
        if target in ("tiff","pdf","webp"):
            assert detect(result.outputs[0]).frames==2
        else:
            assert len(result.outputs)==2 and result.location.is_dir()
            assert all(detect(f).format==target for f in result.outputs)
    pdf=next(tmp_path.glob("*.pdf"))
    result=convert(pdf,"png")
    assert len(result.outputs)==2
    assert not any(r.target=="txt" for r in routes(detect(pdf)))


@pytest.mark.integration
def test_spreadsheet_all_sheets_and_mixed_batch(samples,tmp_path):
    p=tmp_path/"dos hojas.ods"; shutil.copyfile(samples["ods"],p)
    result=convert(p,"csv")
    assert len(result.outputs)==2 and result.location.is_dir()
    assert all("42" in f.read_text() and "Convertix" in f.read_text() for f in result.outputs)
    choices=common_routes([detect(samples["odt"]),detect(samples["png"])])
    assert [r.target for r in choices]==["pdf"]


def test_network_denial_in_worker():
    import sys
    script="""from convertix.security import restrict_worker
import socket
restrict_worker(10)
for family in (socket.AF_INET,socket.AF_INET6):
 try: socket.socket(family)
 except PermissionError: pass
 else: raise AssertionError('network socket allowed')
sock=socket.socket(socket.AF_UNIX); sock.close()
"""
    env=os.environ.copy(); env["PYTHONPATH"]=str(Path(__file__).resolve().parents[1]/"src")
    subprocess.run([sys.executable,"-c",script],env=env,check=True)


@pytest.mark.integration
@pytest.mark.parametrize("origin,base,filter_name",[("doc","odt","MS Word 97"),
    ("xls","ods","MS Excel 97"),("ppt","odp","MS PowerPoint 97")])
def test_legacy_office_content_and_routes(origin,base,filter_name,samples,tmp_path):
    from convertix.process import private_env
    profile=tmp_path/"fixture-profile"
    run(["libreoffice",f"-env:UserInstallation={profile.as_uri()}","--headless","--convert-to",
         f"{origin}:{filter_name}","--outdir",str(tmp_path),str(samples[base])],env=private_env(tmp_path))
    source=tmp_path/f"ejemplo.{origin}"
    assert source.exists() and detect(source).format==origin
    before=sha(source)
    for route in routes(detect(source)):
        result=convert(source,route.target)
        assert all(p.stat().st_size>0 for p in result.outputs)
    assert sha(source)==before


def test_orientation_and_resource_limits(tmp_path):
    p=tmp_path/"orientación.jpg"
    image=Image.new("RGB",(80,40),"green");exif=Image.Exif();exif[274]=6
    image.save(p,exif=exif)
    output=convert(p,"png").outputs[0]
    with Image.open(output) as result:
        assert result.size==(40,80) and result.getexif().get(274,1)==1
    huge=tmp_path/"demasiado-grande.txt"
    with huge.open('wb') as f:f.truncate(513*1024*1024)
    with pytest.raises(ConversionError,match="512"):
        convert(huge,"pdf")


@pytest.mark.integration
def test_pdf_extractable_text(samples,tmp_path):
    source=tmp_path/"texto.odp";shutil.copyfile(samples['odp'],source)
    pdf=convert(source,'pdf').outputs[0]
    detected=detect(pdf)
    assert detected.has_text and detected.frames==2
    assert 'txt' in {r.target for r in routes(detected)}
    before=sha(pdf)
    text=convert(pdf,'txt').outputs[0].read_text()
    assert text.count('Convertix')==2 and '123' in text
    assert sha(pdf)==before


def test_private_source_keeps_private_outputs(tmp_path):
    p=tmp_path/'privado.png';Image.new('RGB',(30,20),'red').save(p);p.chmod(0o600)
    result=convert(p,'jpg')
    assert result.outputs[0].stat().st_mode & 0o777==0o600

