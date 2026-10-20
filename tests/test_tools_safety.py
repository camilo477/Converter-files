import os
import shutil
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from PIL import Image
from convertix.models import ConversionError,Cancelled
from convertix.tools.service import perform,batch


@pytest.mark.parametrize('fmt',['zip','7z'])
def test_archives_unicode_nested_empty_folders_duplicate_names(tmp_path,fmt):
    if fmt=='7z' and not shutil.which('7z'):pytest.skip('7z no está instalado')
    folder=tmp_path/'Carpeta café';folder.mkdir();(folder/'vacía').mkdir();(folder/'a.txt').write_text('Convertix ñ')
    other=tmp_path/'otra';other.mkdir();same=other/'a.txt';same.write_text('otra versión')
    records=[folder,folder/'a.txt',same]
    result=perform('archive',records,{'archive_format':fmt})
    assert result.location.stat().st_size and (folder/'a.txt').read_text()=='Convertix ñ'
    if fmt=='zip':
        with zipfile.ZipFile(result.location) as archive:
            assert archive.testzip() is None
            assert archive.read('Carpeta café/a.txt').decode()=='Convertix ñ'
            assert archive.read('a.txt').decode()=='Convertix ñ'
            assert archive.read('a (2).txt').decode()=='otra versión'
            assert 'Carpeta café/vacía/' in archive.namelist()
            assert all(not n.startswith('/') and '..' not in Path(n).parts for n in archive.namelist())


def test_zip_rejects_symlink_special_and_unsafe_destination(tmp_path):
    folder=tmp_path/'carpeta';folder.mkdir();(folder/'enlace').symlink_to('/etc/passwd')
    with pytest.raises(ConversionError):perform('archive',[folder])
    with pytest.raises(ConversionError,match='fuera'):perform('archive',[folder],destination=folder)
    (folder/'enlace').unlink();os.mkfifo(folder/'fifo')
    with pytest.raises(ConversionError):perform('archive',[folder])
    assert not list(tmp_path.glob('*.zip')) and not list(tmp_path.glob('.convertix-*'))


@pytest.mark.parametrize('name',['../escape','/tmp/escape','a/b','a\\b','..','\x00'])
def test_unsafe_output_names_do_not_publish(tmp_path,name):
    path=tmp_path/'foto.png';Image.new('RGB',(30,20)).save(path)
    with pytest.raises(ConversionError):perform('resize',[path],{'percent':50},name=name)
    assert len(list(tmp_path.iterdir()))==1


def test_concurrent_publication_permissions_and_originals(tmp_path):
    path=tmp_path/'privada ñ.png';Image.new('RGB',(60,40),'red').save(path);path.chmod(0o600);before=path.read_bytes()
    with ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(lambda _:perform('resize',[path],{'percent':50}),range(3)))
    assert len({r.location for r in results})==3
    assert all(r.location.stat().st_mode & 0o777==0o600 for r in results)
    assert path.read_bytes()==before


def test_cancel_preparation_and_pending_batch(tmp_path):
    paths=[]
    for i in range(3):
        path=tmp_path/f'foto{i}.png';Image.new('RGB',(80,60)).save(path);paths.append(path)
    event=threading.Event()
    def progress(message):event.set()
    with pytest.raises(Cancelled):perform('archive',paths,cancel=event,progress=progress)
    assert not list(tmp_path.glob('.convertix-*')) and not list(tmp_path.glob('*.zip'))
    records=batch('resize',paths,{'percent':50},cancel=event)
    assert len(records)==3 and not any(r['ok'] for r in records)


def test_cancel_worker_and_cleanup(tmp_path):
    path=tmp_path/'ruido.bin';path.write_bytes(os.urandom(24*1024*1024))
    cancel=threading.Event()
    def progress(message):
        if message.startswith('Comprimiendo'):cancel.set()
    with pytest.raises(Cancelled):perform('archive',[path],cancel=cancel,progress=progress)
    assert path.stat().st_size==24*1024*1024 and not list(tmp_path.glob('.convertix-*')) and not list(tmp_path.glob('*.zip'))


def test_changed_preview_file_is_rejected(tmp_path):
    from convertix.tools.inspection import inspect_file
    path=tmp_path/'original.png';Image.new('RGB',(30,20),'blue').save(path)
    info=inspect_file(path)
    Image.new('RGB',(40,30),'red').save(path)
    with pytest.raises(ConversionError,match='cambió'):perform('resize',[path],{'percent':50,'fingerprints':{str(path):info['fingerprint']}})
    assert len(list(tmp_path.iterdir()))==1


@pytest.mark.parametrize('options',[{'keep_larger':'false'},{'allow_signed':'false'},{'percent':float('nan')},{'metadata_mode':'unknown'}])
def test_ambiguous_options_rejected(tmp_path,options):
    path=tmp_path/'foto.png';Image.new('RGB',(60,40)).save(path)
    with pytest.raises(ConversionError):perform('resize',[path],options)
    assert len(list(tmp_path.iterdir()))==1


def test_deep_folder_tree_is_rejected_and_cleaned(tmp_path):
    folder=tmp_path/'arbol';folder.mkdir();node=folder
    for _ in range(70):
        node=node/'n';node.mkdir()
    (node/'archivo.txt').write_text('original')
    with pytest.raises(ConversionError,match='64 niveles'):perform('archive',[folder])
    assert (node/'archivo.txt').read_text()=='original'
    assert not list(tmp_path.glob('.convertix-*')) and not list(tmp_path.glob('*.zip'))
