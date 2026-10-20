import time
from pathlib import Path
import pytest
import pymupdf
from PIL import Image
from PySide6.QtCore import Qt,QPointF
from PySide6.QtQuick import QQuickWindow
from PySide6.QtTest import QTest
from convertix.config import Preferences
from convertix.detect import detect
from convertix.gui import Controller,create_engine
from convertix.registry import common_routes
from test_gui import visual_items


def wait(predicate,seconds=30):
    deadline=time.monotonic()+seconds
    while not predicate() and time.monotonic()<deadline:QTest.qWait(20)
    assert predicate()


def setup_window(paths,theme='dark'):
    c=Controller(paths);c.prefs=Preferences(theme=theme,animations=False,notifications=False)
    sources=[detect(p) for p in paths]
    c.scanned((sources,common_routes(sources,c.prefs)))
    e=create_engine(c);w=e.rootObjects()[0];w.show();QTest.qWait(80)
    errors=[];e.warnings.connect(lambda messages:errors.extend(m.toString() for m in messages))
    return c,e,w,errors


def open_tool(c,w,action):
    c.setCategory('modify');c.start('tool:'+action)
    wait(lambda:c.tool.state!='loading')
    assert c.tool.state=='configure',c.tool.message
    child=w.findChild(QQuickWindow,'toolWindow');assert child and child.isVisible()
    QTest.qWait(80)
    return child


def finish(c,e,w):
    c.tool.cancel();wait(lambda:not c._jobs)
    w.close();e.deleteLater();QTest.qWait(50)


@pytest.mark.gui
@pytest.mark.parametrize('theme',['dark','light'])
@pytest.mark.parametrize('action',['pdf-merge','pdf-split','optimize','archive','crop','resize','images-pdf','metadata'])
def test_configuration_windows_and_runtime_qml(qt_app,tmp_path,theme,action):
    if action.startswith('pdf-'):
        paths=[]
        for i in range(2 if action=='pdf-merge' else 1):
            p=tmp_path/f'documento {i}.pdf'
            with pymupdf.open() as d:
                for n in range(5):d.new_page().insert_text((40,50),f'Pagina {n+1}')
                d.save(p)
            paths.append(p)
    else:
        p=tmp_path/'imagen.png';Image.new('RGBA',(300,200),(80,120,160,128)).save(p);paths=[p]
    c,e,w,errors=setup_window(paths,theme)
    child=open_tool(c,w,action)
    assert child.width()>=400 and child.height()>=400
    wait(lambda:not c._jobs)
    assert not errors,'\n'.join(errors)
    finish(c,e,w)


@pytest.mark.gui
def test_category_navigation_and_real_resize(qt_app,tmp_path):
    p=tmp_path/'foto.png';Image.new('RGBA',(100,60),(120,30,70,100)).save(p)
    c,e,w,errors=setup_window([p])
    button=next(i for i in visual_items(w.contentItem()) if i.objectName()=='modifyCategory')
    QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,button.mapToScene(QPointF(button.width()/2,button.height()/2)).toPoint())
    assert c.category=='modify'
    assert {'tool:crop','tool:resize','tool:archive'} <= {o['target'] for o in c.options}
    child=open_tool(c,w,'resize');wait(lambda:not c._jobs)
    execute=next(i for i in visual_items(child.contentItem()) if i.objectName()=='executeTool')
    QTest.mouseClick(child,Qt.LeftButton,Qt.NoModifier,execute.mapToScene(QPointF(execute.width()/2,execute.height()/2)).toPoint())
    wait(lambda:c.state in ('done','error'));wait(lambda:not c._jobs)
    assert c.state=='done',c.details
    with Image.open(c.records[0]['location']) as image:assert image.size==(50,30)
    assert not errors
    finish(c,e,w)


@pytest.mark.gui
def test_crop_visual_coordinates_match_output(qt_app,tmp_path):
    p=tmp_path/'cuadros.png';image=Image.new('RGB',(400,200),'blue');image.paste('red',(200,0,400,200));image.save(p)
    c,e,w,errors=setup_window([p]);child=open_tool(c,w,'crop');wait(lambda:not c._jobs)
    region=next(i for i in visual_items(child.contentItem()) if i.objectName()=='cropRegion')
    editor=next(i for i in visual_items(child.contentItem()) if i.objectName()=='cropEditor')
    # Drag the left edge to the middle using the actual QML handle, then verify pixels.
    handle=next(i for i in visual_items(child.contentItem()) if i.objectName()=='cropHandle_0')
    start=handle.mapToScene(QPointF(7,7)).toPoint()
    end=region.mapToScene(QPointF(region.width()/2,0)).toPoint()
    QTest.mousePress(child,Qt.LeftButton,Qt.NoModifier,start)
    QTest.mouseMove(child,end,80);QTest.mouseRelease(child,Qt.LeftButton,Qt.NoModifier,end)
    QTest.qWait(80)
    # Read the selected coordinates from the same component used by the Execute button.
    box=editor.property('box')
    if hasattr(box,'toVariant'):box=box.toVariant()
    assert abs(box[0]-200)<=3 and box[1]==0 and box[2:]==[400,200],box
    c.tool.execute({'box':box});wait(lambda:c.state in ('done','error'));wait(lambda:not c._jobs)
    assert c.state=='done',c.details
    with Image.open(c.records[0]['location']) as result:
        assert result.size==(400-box[0],200)
        assert result.getpixel((result.width//2,100))==(255,0,0)
    assert not errors
    finish(c,e,w)


@pytest.mark.gui
def test_drag_order_and_page_selection(qt_app,tmp_path):
    paths=[]
    for i in range(3):
        p=tmp_path/f'documento {i}.pdf'
        with pymupdf.open() as doc:
            for n in range(30):doc.new_page().insert_text((30,50),f'Documento {i} pagina {n}')
            doc.save(p)
        paths.append(p)
    c,e,w,errors=setup_window(paths);child=open_tool(c,w,'pdf-merge');wait(lambda:not c._jobs)
    handle=next(i for i in visual_items(child.contentItem()) if i.objectName()=='dragRow_0')
    start=handle.mapToScene(QPointF(15,30)).toPoint();end=start+__import__('PySide6.QtCore',fromlist=['QPoint']).QPoint(0,165)
    QTest.mousePress(child,Qt.LeftButton,Qt.NoModifier,start);QTest.mouseMove(child,end,90);QTest.mouseMove(child,end,30);QTest.mouseRelease(child,Qt.LeftButton,Qt.NoModifier,end)
    QTest.qWait(80)
    assert c.tool.files[-1]==paths[0]
    c.tool.cancel();wait(lambda:not c._jobs)
    c.files=paths[:1];c.sources=[detect(paths[0])];c.scanned((c.sources,common_routes(c.sources)))
    child=open_tool(c,w,'pdf-split');wait(lambda:not c._jobs)
    assert len(c.tool.cache)<30,'Las miniaturas deben cargarse según la vista, sin renderizar todo el PDF'
    tile=next(i for i in visual_items(child.contentItem()) if i.objectName()=='pageTile_2')
    QTest.mouseClick(child,Qt.LeftButton,Qt.NoModifier,tile.mapToScene(QPointF(50,65)).toPoint())
    field=next(i for i in visual_items(child.contentItem()) if i.objectName()=='pageRanges')
    assert field.property('text')=='3'
    assert not errors
    finish(c,e,w)


@pytest.mark.gui
def test_tool_palette_updates_with_theme(qt_app,tmp_path):
    p=tmp_path/'foto.png';Image.new('RGB',(120,80)).save(p)
    c,e,w,errors=setup_window([p],'dark')
    c.prefs.theme='light';c.preferencesChanged.emit()
    child=open_tool(c,w,'crop');wait(lambda:not c._jobs)
    heading=next(i for i in visual_items(child.contentItem()) if i.objectName()=='toolFileHeading')
    assert heading.property('color').lightnessF()<0.4
    c.prefs.theme='dark';c.preferencesChanged.emit();QTest.qWait(60)
    assert heading.property('color').lightnessF()>0.7
    assert not errors
    finish(c,e,w)


@pytest.mark.gui
@pytest.mark.parametrize('index,ratio',[(1,1),(4,16/9)])
def test_crop_aspect_presets_export_selected_ratio(qt_app,tmp_path,index,ratio):
    p=tmp_path/'foto.png';Image.new('RGBA',(400,260),(60,100,140,128)).save(p)
    c,e,w,errors=setup_window([p]);child=open_tool(c,w,'crop');wait(lambda:not c._jobs)
    combo=next(i for i in visual_items(child.contentItem()) if i.objectName()=='cropAspect')
    combo.setProperty('currentIndex',index);QTest.qWait(50)
    editor=next(i for i in visual_items(child.contentItem()) if i.objectName()=='cropEditor')
    box=editor.property('box');box=box.toVariant() if hasattr(box,'toVariant') else box
    width,height=box[2]-box[0],box[3]-box[1]
    assert abs(width/height-ratio)<0.015
    c.tool.execute({'box':box});wait(lambda:c.state in ('done','error'));wait(lambda:not c._jobs)
    assert c.state=='done',c.details
    with Image.open(c.records[0]['location']) as output:assert output.size==(width,height)
    assert not errors
    finish(c,e,w)
