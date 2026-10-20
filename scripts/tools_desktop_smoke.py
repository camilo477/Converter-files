#!/usr/bin/env python3
"""Installed native Qt tool windows; distinct from Dolphin context-menu acceptance."""
import hashlib
import argparse
import json
import time
from pathlib import Path
from PIL import Image
import pymupdf
from PySide6.QtCore import Qt,QPointF
from PySide6.QtQuick import QQuickWindow
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from convertix.cli import setup_logging
from convertix.gui import Controller,create_engine
import convertix.tools.gui as tool_gui


def items(root):
    for item in root.childItems():
        yield item;yield from items(item)


def wait(predicate,seconds=90):
    deadline=time.monotonic()+seconds
    while not predicate() and time.monotonic()<deadline:QTest.qWait(25)
    assert predicate()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--preview-only',action='store_true');args=parser.parse_args()
    project=Path(__file__).resolve().parents[1];folder=project/'examples/v21'
    app=QApplication([]);app.setQuitOnLastWindowClosed(False);setup_logging()
    notifications=[];real_notify=tool_gui.notify
    def observed(*args):
        result=real_notify(*args);notifications.append(result);return result
    tool_gui.notify=observed
    cases=[('pdf-merge',[folder/'Documento 1.pdf',folder/'Documento 2.pdf'],'merge'),
           ('pdf-split',[folder/'Documento 1.pdf'],'split'),
           ('optimize',[folder/'Documento 1.pdf'],'optimize-pdf'),
           ('optimize',[folder/'Imagen 1.png'],'optimize-image'),
           ('archive',[folder/'Carpeta para ZIP',folder/'Foto con EXIF.jpg'],'zip'),
           ('archive',[folder/'Carpeta para ZIP',folder/'Foto con EXIF.jpg'],'7z'),
           ('crop',[folder/'Imagen 1.png'],'crop'),
           ('resize',[folder/f'Imagen {i}.png' for i in (1,2,3)],'resize'),
           ('images-pdf',[folder/f'Imagen {i}.png' for i in (1,2,3)],'images-pdf'),
           ('metadata',[folder/'Foto con EXIF.jpg'],'metadata-jpg'),
           ('metadata',[folder/'Documento 1.pdf'],'metadata-pdf')]
    records=[]
    for action,paths,label in cases:
        before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}
        c=Controller(paths);c.prefs.theme='dark';c.prefs.animations=False
        e=create_engine(c);w=e.rootObjects()[0];w.show();w.requestActivate();c.scan()
        wait(lambda:c.state!='scanning');assert c.state=='ready',c.details;wait(lambda:not c._jobs)
        c.setCategory('modify')
        if args.preview_only:
            # Capture mode opens configuration directly before compositor focus changes.
            # The independent functional run uses real radial mouse events below.
            c.start('tool:'+action)
        QTest.qWait(100)
        if label=='merge':w.grabWindow().save(str(project/'docs/v21-radial-dark.png'))
        if label=='crop':
            c.prefs.theme='light';c.preferencesChanged.emit();QTest.qWait(100)
            w.grabWindow().save(str(project/'docs/v21-radial-light.png'))
        if not args.preview_only:
            option=next(i for i in items(w.contentItem()) if i.objectName()=='target_tool:'+action)
            QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,option.mapToScene(QPointF(option.width()/2,option.height()/2)).toPoint())
        wait(lambda:c.tool.state!='loading');assert c.tool.state=='configure',c.tool.message
        child=w.findChild(QQuickWindow,'toolWindow');assert child and child.isVisible();wait(lambda:not c._jobs)
        def named(name):return next(i for i in items(child.contentItem()) if i.objectName()==name)
        if label=='split':
            named('splitMode').setProperty('currentIndex',3);named('pageRanges').setProperty('text','1-2;3-4')
        if label=='7z':
            named('archiveFormat').setProperty('currentIndex',1);named('toolOutputName').setProperty('text','archivos.7z')
        if label=='crop':
            editor=named('cropEditor');editor.setProperty('cropX',100);editor.setProperty('cropY',50);editor.setProperty('cropWidth',400);editor.setProperty('cropHeight',300)
        if label=='metadata-pdf':
            named('cleaningMode').setProperty('currentIndex',1);named('removeAttachments').setProperty('checked',True)
        QTest.qWait(150);child.grabWindow().save(str(project/f'docs/v21-tool-{label}.png'))
        if args.preview_only:
            c.tool.cancel();wait(lambda:not c._jobs);w.close();e.deleteLater();QTest.qWait(100)
            records.append({'case':label,'captured':True});print(label,'CAPTURED',flush=True)
            continue
        button=named('executeTool');QTest.mouseClick(child,Qt.LeftButton,Qt.NoModifier,button.mapToScene(QPointF(button.width()/2,button.height()/2)).toPoint())
        wait(lambda:c.state in ('done','error'));wait(lambda:not c._jobs)
        assert c.state=='done',c.details
        for r in c.records:assert Path(r['location']).exists()
        assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==value for p,value in before.items())
        if label=='merge':
            with pymupdf.open(c.records[0]['location']) as d:assert len(d)==6
        if label=='crop':
            with Image.open(c.records[0]['location']) as image:assert image.size==(400,300)
        records.append({'action':action,'case':label,'records':c.records,'original_sha256':before,
                        'originals_unchanged':True,'notification_accepted':notifications[-1] is True,'radial_mouse_selection':True,'execute_mouse_selection':True})
        w.grabWindow().save(str(project/f'docs/v21-completed-{label}.png'))
        w.close();e.deleteLater();QTest.qWait(100)
        print(label,'OK',flush=True)
    result={'platform':app.platformName(),'cases':records,'dolphin_context_menu':'independent; not implied by this test'}
    (project/('docs/v21-preview-captures.json' if args.preview_only else 'docs/v21-desktop-tools.json')).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'platform':app.platformName(),'cases':len(records),'passed':True}))


if __name__=='__main__':main()
