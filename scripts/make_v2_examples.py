#!/usr/bin/env python3
"""Create local synthetic examples; refuses to replace an existing examples/v2 folder."""
from pathlib import Path


def make_examples(project: Path) -> Path:
    import pymupdf
    folder=project/'examples/v2'
    folder.mkdir()
    document=pymupdf.open();page=document.new_page()
    page.insert_text((50,65),'Convertix 2.0',fontsize=24)
    page.insert_text((50,110),'Texto editable en español: café, año y conversión.',fontsize=13)
    page.insert_text((50,145),'English example: local document conversion.',fontsize=13)
    for x in [50,300,500]:page.draw_line((x,200),(x,350),width=1)
    for y in [200,250,300,350]:page.draw_line((50,y),(500,y),width=1)
    for r,row in enumerate([['Producto','Cantidad'],['Café','42'],['Documento','123']]):
        for c,value in enumerate(row):page.insert_text((60+c*250,230+r*50),value,fontsize=13)
    document.save(folder/'PDF digital con tabla.pdf')
    scanned=pymupdf.open();p=scanned.new_page(width=page.rect.width,height=page.rect.height)
    p.insert_image(p.rect,stream=page.get_pixmap(dpi=200).tobytes('png'))
    scanned.save(folder/'PDF escaneado.pdf')
    mixed=pymupdf.open();mixed.new_page();mixed.insert_pdf(document);mixed.insert_pdf(scanned)
    mixed.save(folder/'PDF mixto con portada vacía.pdf')
    return folder


if __name__=='__main__':print(make_examples(Path(__file__).resolve().parents[1]))
