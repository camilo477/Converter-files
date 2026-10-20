#!/usr/bin/env python3
"""Synthetic, non-personal inputs for the editing tools; refuse to overwrite."""
from pathlib import Path
import io
import pymupdf
from PIL import Image,PngImagePlugin


def main():
    folder=Path(__file__).resolve().parents[1]/'examples/v21'
    folder.mkdir(exist_ok=False)
    for number,count in [(1,4),(2,2)]:
        with pymupdf.open() as doc:
            for page in range(count):
                p=doc.new_page(width=420 if page%2==0 else 595,height=595 if page%2==0 else 420)
                p.insert_text((35,48),f'Convertix 2.1 - Documento {number} - Pagina {page+1}',fontsize=16)
                p.insert_text((35,85),'Archivo sintetico. Texto seleccionable. Original protegido.',fontsize=11)
                a=p.add_text_annot((35,120),'Comentario de prueba visible');a.set_info(title='Autor sintetico')
                if page==0:
                    image=Image.effect_noise((900,1000),35).convert('RGB');data=io.BytesIO();image.save(data,'PNG')
                    p.insert_image(pymupdf.Rect(35,160,385,550),stream=data.getvalue())
            doc.set_metadata({'author':'Autor de prueba','title':'Metadatos sinteticos','creator':'Convertix ejemplos'})
            doc.set_xml_metadata('<x:xmpmeta xmlns:x="adobe:ns:meta/">informacion sintetica</x:xmpmeta>')
            doc.set_toc([[1,'Primera pagina',1],[1,'Ultima pagina',count]])
            doc.embfile_add('prueba.txt',b'Adjunto sintetico para comprobar limpieza')
            doc.save(folder/f'Documento {number}.pdf')
    for number,color in enumerate(['#c05258','#459d79','#4c87bd'],1):
        image=Image.new('RGBA',(640+number*80,480),(0,0,0,0))
        image.paste(color,(40,30,image.width//2,image.height-30))
        image.paste('#eac15c',(image.width//2,30,image.width-40,image.height-30))
        text=PngImagePlugin.PngInfo();text.add_text('Autor','Persona sintetica')
        image.save(folder/f'Imagen {number}.png',pnginfo=text,compress_level=0)
    image=Image.new('RGB',(600,400),'#6688aa');exif=Image.Exif();exif[315]='Autor sintetico';exif[305]='Software de prueba';exif[34853]={1:'N',2:(0,0,0)}
    image.save(folder/'Foto con EXIF.jpg',quality=95,exif=exif)
    archive=folder/'Carpeta para ZIP';archive.mkdir();(archive/'Vacía').mkdir();(archive/'Archivo ñ.txt').write_text('Datos sinteticos de Convertix 2.1\n'*100)
    print(folder)


if __name__=='__main__':main()
