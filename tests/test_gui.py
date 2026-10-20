from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt, Slot
from PySide6.QtTest import QTest
from PySide6.QtQuick import QQuickItem

from convertix.gui import Controller, create_engine
from convertix.config import Preferences


def visual_items(item):
    for child in item.childItems():
        yield child
        yield from visual_items(child)


class FakeController(Controller):
    def __init__(self, count):
        super().__init__([Path("documento café.docx")])
        self.state="ready"
        self.options=[{"target":f"fmt{i}","label":f"FMT{i}","icon":"application-pdf","accent":"#619fea","hint":"Descripción de prueba"} for i in range(count)]
        self.started=[]

    @Slot(str)
    def start(self,target):
        self.started.append(target)


@pytest.mark.gui
@pytest.mark.parametrize("count", [0,2,3,6,8,12])
def test_layout_keyboard_and_escape(qt_app,count):
    c=FakeController(count)
    if not count: c.state="unavailable"
    e=create_engine(c); assert e.rootObjects()
    w=e.rootObjects()[0]; w.show()
    assert QTest.qWaitForWindowExposed(w, 3000)
    w.requestActivate(); QTest.qWait(150)
    next(i for i in visual_items(w.contentItem()) if i.objectName()=="keyArea").forceActiveFocus()
    assert w.isVisible()
    items=[item for item in visual_items(w.contentItem()) if item.objectName().startswith("target_")]
    assert len(items)==min(count,8)
    for i,a in enumerate(items):
        assert 12<=a.x() and a.x()+a.width()<=628
        assert 75<=a.y() and a.y()+a.height()<=564
        for b in items[i+1:]:
            assert abs(a.x()-b.x())>=a.width() or abs(a.y()-b.y())>=a.height()
    if count:
        QTest.keyClick(w,Qt.Key_Right)
        QTest.keyClick(w,Qt.Key_Return)
        assert c.started==["fmt1"]
        if count>8:
            QTest.keyClick(w,Qt.Key_PageDown); QTest.keyClick(w,Qt.Key_Return)
            assert c.started[-1]=="fmt8"
    QTest.keyClick(w,Qt.Key_Escape); QTest.qWait(300)
    assert not w.isVisible()
    e.deleteLater(); qt_app.processEvents()


@pytest.mark.gui
@pytest.mark.parametrize("theme",["light","dark"])
def test_mouse_theme_and_hidpi_scaling(qt_app,theme):
    c=FakeController(6); c.prefs.theme=theme
    e=create_engine(c); w=e.rootObjects()[0]; w.setProperty("uiScale",0.75); w.show(); QTest.qWait(80)
    assert w.width()==480
    assert w.property("dark")== (theme=="dark")
    item=next(item for item in visual_items(w.contentItem()) if item.objectName()=="target_fmt2")
    point=item.mapToScene(QPointF(item.width()/2,item.height()/2)).toPoint()
    QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,point)
    assert c.started==["fmt2"]
    w.close(); e.deleteLater(); qt_app.processEvents()


@pytest.mark.gui
@pytest.mark.parametrize("cancel_after_first",[False,True])
def test_real_batch_and_pending_cancellation(qt_app,tmp_path,monkeypatch,cancel_after_first):
    import time
    from PIL import Image
    import convertix.gui as gui
    files=[]
    for i in range(3):
        p=tmp_path/f"lote {i} café.png";Image.new("RGB",(60,40),(i*40,60,80)).save(p);files.append(p)
    c=Controller(files);c.prefs=Preferences(notifications=False)
    c.scan()
    def wait_until(predicate,seconds=20):
        deadline=time.monotonic()+seconds
        while not predicate() and time.monotonic()<deadline: QTest.qWait(15)
        assert predicate()
    wait_until(lambda:c.state not in ("scanning",))
    assert c.state=='ready'
    if cancel_after_first:
        original=gui.convert
        def wrapped(*args,**kwargs):
            result=original(*args,**kwargs)
            c.cancel_event.set()
            return result
        monkeypatch.setattr(gui,'convert',wrapped)
    c.start('pdf')
    c.start('pdf')  # The second activation must not launch another batch.
    wait_until(lambda:c.state in ('done','error'))
    wait_until(lambda:not c._jobs)
    assert len(c.records)==3
    successes=sum(r['ok'] for r in c.records)
    assert successes==(1 if cancel_after_first else 3)
    assert len(list(tmp_path.glob('*.pdf')))==successes
    assert all(p.exists() for p in files)


@pytest.mark.gui
def test_close_on_focus_loss(qt_app):
    from PySide6.QtGui import QWindow
    c=FakeController(3);e=create_engine(c);w=e.rootObjects()[0];w.show();w.requestActivate()
    QTest.qWait(180);w.setProperty('hadFocus',True)
    other=QWindow();other.setTitle('Convertix focus test');other.resize(100,100);other.show();other.requestActivate()
    QTest.qWait(500)
    if w.isActive():
        other.close();w.close();e.deleteLater();qt_app.processEvents()
        pytest.skip("El compositor no concedió activar la segunda ventana sin un gesto físico; pérdida de foco pendiente de prueba manual")
    assert not w.isVisible()
    other.close();e.deleteLater();qt_app.processEvents()


@pytest.mark.gui
@pytest.mark.parametrize('theme',['light','dark'])
def test_real_alpha_and_independent_button_opacity(qt_app,theme):
    c=FakeController(6);c.prefs.theme=theme
    e=create_engine(c);w=e.rootObjects()[0];w.show();QTest.qWait(300)
    for transparency,expected in [(85,38),(100,0),(0,255)]:
        c.prefs.radial_transparency=transparency;c.preferencesChanged.emit();QTest.qWait(80)
        image=w.grabWindow()
        assert image.hasAlphaChannel()
        assert image.pixelColor(30,180).alpha()==0
        assert abs(image.pixelColor(205,300).alpha()-expected)<=2
        assert image.pixelColor(285,145).alpha()>=215
    w.close();e.deleteLater();qt_app.processEvents()

