import os
import subprocess
import sys
from pathlib import Path
from convertix import __version__


def test_install_update_conflict_and_uninstall(tmp_path):
    project=Path(__file__).resolve().parents[1]
    prefix=tmp_path/"prefijo con espacios ñ"
    install=[sys.executable,str(project/"scripts/install.py"),"--prefix",str(prefix)]
    subprocess.run(install,check=True,capture_output=True)
    launcher=prefix/"bin/convertix"
    assert subprocess.check_output([str(launcher),"--version"],cwd="/tmp",text=True).strip()==__version__
    hostile=tmp_path/"hostile";hostile.mkdir();(hostile/"convertix.py").write_text("raise RuntimeError('untrusted cwd executed')")
    assert subprocess.check_output([str(launcher),"--version"],cwd=hostile,text=True).strip()==__version__
    service=prefix/"share/kio/servicemenus/convertix.desktop"
    assert os.access(service,os.X_OK) and "X-KDE-Priority=TopLevel" in service.read_text()
    subprocess.run(install,check=True,capture_output=True)
    service.write_text(service.read_text()+"# cambio manual\n")
    failed=subprocess.run(install,capture_output=True,text=True)
    assert failed.returncode!=0 and "No se sobrescribe" in failed.stderr
    subprocess.run([str(prefix/"bin/convertix-uninstall")],check=True,capture_output=True)
    assert not launcher.exists() and not (prefix/"share/convertix").exists()
    assert service.exists()  # Manually edited files are preserved by the uninstaller.

