#!/usr/bin/env python3
"""Optional real Dolphin acceptance test using AT-SPI and a controlled XWayland window.

No production code uses X11 input injection. KWin-native input may be unavailable;
this test records its backend and never equates XWayland with native Wayland.
Only synthetic files and a temporary Dolphin configuration are used.
"""
import argparse
import ctypes as C
import ctypes.util
import hashlib
import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path


def context_key_for_pid(pid):
    x = C.CDLL(ctypes.util.find_library('X11'))
    xt = C.CDLL(ctypes.util.find_library('Xtst'))
    D = C.c_void_p; W = C.c_ulong
    x.XOpenDisplay.argtypes=[C.c_char_p];x.XOpenDisplay.restype=D
    x.XDefaultRootWindow.argtypes=[D];x.XDefaultRootWindow.restype=W
    x.XInternAtom.argtypes=[D,C.c_char_p,C.c_int];x.XInternAtom.restype=W
    x.XGetWindowProperty.argtypes=[D,W,W,C.c_long,C.c_long,C.c_int,W,C.POINTER(W),C.POINTER(C.c_int),C.POINTER(W),C.POINTER(W),C.POINTER(C.POINTER(C.c_ubyte))]
    x.XQueryTree.argtypes=[D,W,C.POINTER(W),C.POINTER(W),C.POINTER(C.POINTER(W)),C.POINTER(C.c_uint)]
    x.XFree.argtypes=[D]
    x.XMapRaised.argtypes=[D,W];x.XSetInputFocus.argtypes=[D,W,C.c_int,W]
    x.XKeysymToKeycode.argtypes=[D,W];x.XKeysymToKeycode.restype=C.c_uint
    xt.XTestFakeKeyEvent.argtypes=[D,C.c_uint,C.c_int,W]
    x.XSync.argtypes=[D,C.c_int];x.XCloseDisplay.argtypes=[D]
    display=x.XOpenDisplay(None)
    if not display:raise RuntimeError('XWayland display unavailable')
    atom=x.XInternAtom(display,b'_NET_WM_PID',0)
    def find(window,depth=0):
        actual=W();fmt=C.c_int();count=W();after=W();data=C.POINTER(C.c_ubyte)()
        x.XGetWindowProperty(display,window,atom,0,1,0,0,C.byref(actual),C.byref(fmt),C.byref(count),C.byref(after),C.byref(data))
        matched=bool(data) and count.value and C.cast(data,C.POINTER(W))[0]==pid
        if data:x.XFree(data)
        if matched:return window
        if depth>5:return None
        root=W();parent=W();children=C.POINTER(W)();n=C.c_uint()
        if not x.XQueryTree(display,window,C.byref(root),C.byref(parent),C.byref(children),C.byref(n)):return None
        result=None
        for i in range(n.value):
            result=find(children[i],depth+1)
            if result:break
        if children:x.XFree(children)
        return result
    try:
        window=find(x.XDefaultRootWindow(display))
        if not window:raise RuntimeError('No XWayland window for the test Dolphin PID')
        x.XMapRaised(display,window);x.XSetInputFocus(display,window,2,0);x.XSync(display,0)
        code=x.XKeysymToKeycode(display,0xff67)
        xt.XTestFakeKeyEvent(display,code,1,0);xt.XTestFakeKeyEvent(display,code,0,0);x.XSync(display,0)
    finally:x.XCloseDisplay(display)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--prefix',type=Path,default=Path('/tmp/convertix-v2-desktop-prefix'))
    args=parser.parse_args()
    import pyatspi
    from docx import Document
    project=Path(__file__).resolve().parents[1]
    record={'session':os.environ.get('XDG_SESSION_TYPE'),'dolphin_backend':'xcb / XWayland','passed':False,'flows':[]}
    def find(a,predicate,depth=0):
        if depth>20:return None
        try:
            if predicate(a):return a
            for child in a:
                result=find(child,predicate,depth+1)
                if result:return result
        except Exception:pass
        return None
    def wait(fn,timeout=20):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            result=fn()
            if result:return result
            time.sleep(.15)
        raise RuntimeError('Timed out waiting for a desktop action')
    def showing(a):return a.getState().contains(pyatspi.STATE_SHOWING)
    existing={a.get_process_id() for a in pyatspi.Registry.getDesktop(0)}
    app_pids=set();dolphin=None
    with tempfile.TemporaryDirectory(prefix='convertix-dolphin-v2-') as temporary:
        folder=Path(temporary);files=folder/'archivos';files.mkdir()
        shutil.copyfile(project/'examples/Documento de prueba.docx',files/'Entrada Word.docx')
        shutil.copyfile(project/'examples/Documento de prueba.pdf',files/'Entrada PDF.pdf')
        env=os.environ.copy();env.update(QT_QPA_PLATFORM='xcb',QT_LINUX_ACCESSIBILITY_ALWAYS_ON='1',QT_ACCESSIBILITY='1',
            XDG_CONFIG_HOME=str(folder/'config'),XDG_DATA_HOME=str(args.prefix/'share'))
        log=(project/'docs/v2-dolphin-desktop.log').open('w')
        try:
            record['stage']='start_dolphin'
            dolphin=subprocess.Popen(['dolphin','--new-window',str(files)],env=env,stdout=log,stderr=log)
            print('Dolphin PID:',dolphin.pid,flush=True)
            application=wait(lambda:next((a for a in pyatspi.Registry.getDesktop(0) if a.name=='dolphin' and a.get_process_id()==dolphin.pid),None))
            for name,target in [('Entrada Word.docx','PDF'),('Entrada PDF.pdf','DOCX')]:
                record['stage']='locate_source_'+name
                original=files/name;before=hashlib.sha256(original.read_bytes()).hexdigest()
                item=wait(lambda:find(application,lambda a:a.name==name and showing(a)))
                item.parent.querySelection().clearSelection();item.parent.querySelection().selectChild(item.getIndexInParent())
                item.parent.queryComponent().grabFocus();context_key_for_pid(dolphin.pid)
                record['stage']='context_action_'+name
                action=wait(lambda:find(application,lambda a:a.name=='Convertir…' and showing(a)))
                print('Real Dolphin action visible:',name,flush=True)
                assert action.queryAction().doAction(0)
                record['stage']='locate_convertix'
                def converted_app():
                    for a in pyatspi.Registry.getDesktop(0):
                        if a.get_process_id() not in existing and a.name.lower()=='convertix':return a
                    return None
                app=wait(converted_app);app_pids.add(app.get_process_id())
                record['stage']='select_radial_'+target
                option=wait(lambda:find(app,lambda a:a.name=='Convertir a '+target and showing(a)))
                assert option.queryAction().doAction(0)
                output=original.with_suffix('.'+target.lower())
                wait(lambda:output.exists(),45)
                wait(lambda:find(app,lambda a:a.name=='Conversión completada' and showing(a)),15)
                assert hashlib.sha256(original.read_bytes()).hexdigest()==before
                if target=='DOCX':assert any('Convertix' in p.text for p in Document(output).paragraphs)
                else:assert output.read_bytes().startswith(b'%PDF-')
                close=wait(lambda:find(app,lambda a:a.name=='Cerrar' and showing(a)))
                assert close.queryAction().doAction(0)
                wait(lambda:not any(a.get_process_id()==app.get_process_id() for a in pyatspi.Registry.getDesktop(0)),10)
                record['flows'].append({'source':name,'target':target,'context_action':True,'radial_selection':True,'valid_output':True,'original_unchanged':True})
            record['passed']=True
        except Exception as error:
            record['reason']=str(error)
            record['dolphin_exit_code']=dolphin.poll() if dolphin else None
            record['accessible_apps']=[{'name':a.name,'pid':a.get_process_id()} for a in pyatspi.Registry.getDesktop(0) if a.name.lower() in ('convertix','dolphin')]
            visible=[]
            def collect(a,depth=0):
                if depth>20 or len(visible)>100:return
                try:
                    if showing(a) and a.getRoleName() in ('menu item','popup menu'):visible.append(a.name)
                    for child in a:collect(child,depth+1)
                except Exception:pass
            if 'application' in locals():collect(application)
            record['visible_menu_items']=visible
        finally:
            for pid in app_pids:
                try:os.kill(pid,signal.SIGTERM)
                except ProcessLookupError:pass
            if dolphin and dolphin.poll() is None:
                dolphin.terminate()
                try:dolphin.wait(timeout=4)
                except subprocess.TimeoutExpired:dolphin.kill();dolphin.wait()
            log.close()
    (project/'docs/v2-dolphin-result.json').write_text(json.dumps(record,indent=2))
    print(json.dumps(record,indent=2))
    return 0 if record['passed'] else 2


if __name__=='__main__':raise SystemExit(main())
