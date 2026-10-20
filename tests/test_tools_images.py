import io
from pathlib import Path
import pymupdf
import pytest
from PIL import Image,ImageOps,PngImagePlugin
from convertix.models import ConversionError
from convertix.tools.service import perform,batch
from convertix.tools.inspection import inspect_file


def picture(path,fmt='PNG',orientation=1):
    image=Image.new('RGBA',(120,80),(20,40,60,0))
    image.paste((240,30,40,255),(0,0,60,40));image.paste((20,230,50,128),(60,40,120,80))
    exif=Image.Exif();exif[274]=orientation;exif[315]='Autora privada';exif[305]='Software personal'
    exif[34853]={1:'N',2:(1,2,3)}
    # TIFF expects nested EXIF IFDs parsed from bytes, rather than an unbound dict.
    parsed=Image.Exif();parsed.load(exif.tobytes())
    options={'exif':parsed,'dpi':(144,144)}
    if fmt=='JPEG':image=image.convert('RGB')
    if fmt=='PNG':
        text=PngImagePlugin.PngInfo();text.add_text('Autor','Persona privada');options['pnginfo']=text
    image.save(path,fmt,**options)
    return path


@pytest.mark.parametrize('fmt,ext',[('JPEG','jpg'),('PNG','png')])
@pytest.mark.parametrize('orientation',[1,6])
def test_crop_oriented_coordinates_and_alpha(tmp_path,fmt,ext,orientation):
    source=picture(tmp_path/f'foto.{ext}',fmt,orientation);before=source.read_bytes()
    with Image.open(source) as original:
        expected=ImageOps.exif_transpose(original).crop((10,5,50,35)).convert('RGBA')
    result=perform('crop',[source],{'box':[10,5,50,35]})
    with Image.open(result.location) as image:
        assert image.size==(40,30) and image.getexif().get(274,1)==1
        if ext=='png':assert image.convert('RGBA').tobytes()==expected.tobytes()
    assert source.read_bytes()==before


@pytest.mark.parametrize('box',[[-1,0,10,10],[0,0,121,40],[10,10,5,5],[0,0,0,0],[]])
def test_crop_invalid_box(tmp_path,box):
    source=picture(tmp_path/'foto.png')
    with pytest.raises(ConversionError):perform('crop',[source],{'box':box})
    assert len(list(tmp_path.iterdir()))==1


@pytest.mark.parametrize('params,size',[
    ({'percent':50},(60,40)),
    ({'width':100,'height':100},(100,67)),
    ({'width':100,'height':100,'keep_aspect':False},(100,100)),
    ({'percent':200},(240,160)),
    ({'width':60},(60,40))])
def test_resize_geometry(tmp_path,params,size):
    source=picture(tmp_path/'foto.png');result=perform('resize',[source],params)
    with Image.open(result.location) as image:
        assert image.size==size and image.convert('RGBA').getchannel('A').getextrema()[0]==0


def test_resize_batch_different_orientations_and_names(tmp_path):
    paths=[picture(tmp_path/f'foto {i}.png',orientation=6 if i else 1) for i in range(3)]
    records=batch('resize',paths,{'percent':50})
    assert all(r['ok'] for r in records) and len({r['location'] for r in records})==3
    sizes=[]
    for r in records:
        with Image.open(r['location']) as image:sizes.append(image.size)
    assert sizes==[(60,40),(40,60),(40,60)]


@pytest.mark.parametrize('fmt,ext',[('JPEG','jpg'),('PNG','png'),('WEBP','webp'),('TIFF','tiff')])
@pytest.mark.parametrize('mode',['standard','deep'])
def test_image_metadata_and_orientation(tmp_path,fmt,ext,mode):
    source=picture(tmp_path/f'personal.{ext}',fmt,6);before=source.read_bytes()
    result=perform('metadata',[source],{'metadata_mode':mode})
    with Image.open(result.location) as image, Image.open(source) as original:
        expected=ImageOps.exif_transpose(original).convert('RGBA')
        # TIFF's decoder may apply orientation during load; compare actual oriented pixels.
        assert image.size==expected.size
        assert not image.getexif().get(315) and not image.getexif().get(34853)
        assert not getattr(image,'text',{}) and not image.info.get('xmp')
        if ext in ('png','webp','tiff'):
            assert image.convert('RGBA').tobytes()==expected.tobytes()
    assert source.read_bytes()==before


@pytest.mark.parametrize('fmt,ext',[('PNG','png'),('JPEG','jpg'),('WEBP','webp')])
def test_optimize_image_actual_sizes(tmp_path,fmt,ext):
    source=tmp_path/f'grande.{ext}'
    image=Image.effect_noise((800,600),30).convert('RGB')
    image.save(source,fmt,quality=100,compress_level=0)
    result=perform('optimize',[source],{'level':'balanced'})
    assert result.stats['result_bytes']==result.location.stat().st_size<source.stat().st_size
    with Image.open(result.location) as output:assert output.size==(800,600)


def animated(path,fmt='WEBP'):
    frames=[]
    for i in range(3):
        image=Image.new('RGBA',(80,60),(0,0,0,0));image.paste((i*70,100,150,255),(10+i*10,10,30+i*10,30));frames.append(image)
    frames[0].save(path,fmt,save_all=True,append_images=frames[1:],duration=[80,140,210],loop=2,lossless=True,kmin=1,kmax=1)
    return path


@pytest.mark.parametrize('action,params',[('resize',{'percent':50}),('metadata',{}),('optimize',{'level':'lossless','keep_larger':True})])
def test_animated_webp_keeps_frames_times_loop_alpha(tmp_path,action,params):
    source=animated(tmp_path/'animacion.webp');result=perform(action,[source],params)
    with Image.open(result.location) as image:
        assert image.n_frames==3 and image.info['loop']==2
        for i,duration in enumerate([80,140,210]):
            image.seek(i);image.load()
            assert image.info['duration']==duration
            assert image.convert('RGBA').getchannel('A').getextrema()[0]==0


@pytest.mark.parametrize('page_size,expected',[('a4',(595.276,841.89)),('letter',(612,792)),('image',None),('custom',(400,500))])
def test_images_pdf_order_sizes_alpha_and_single(tmp_path,page_size,expected):
    paths=[]
    for i,color in enumerate(['red','green','blue']):
        p=tmp_path/f'imagen {i}.png';Image.new('RGBA',(100+i*10,200),(0,0,0,0)).save(p)
        if i==1:Image.new('RGB',(110,200),color).save(p)
        paths.append(p)
    result=perform('images-pdf',paths[::-1],{'page_size':page_size,'margin_mm':0,'page_width_mm':400*25.4/72,'page_height_mm':500*25.4/72})
    with pymupdf.open(result.location) as doc:
        assert len(doc)==3
        if expected:assert abs(doc[0].rect.width-expected[0])<0.1 and abs(doc[0].rect.height-expected[1])<0.1
        for i in (0,2):
            pix=doc[i].get_pixmap();assert pix.pixel(pix.width//2,pix.height//2)==(255,255,255)
        pix=doc[1].get_pixmap();assert pix.pixel(pix.width//2,pix.height//2)[1]>100
    assert perform('images-pdf',paths[:1],{'page_size':'letter'}).location.exists()


def test_animated_crop_and_images_pdf_are_disabled(tmp_path):
    source=animated(tmp_path/'animacion.webp')
    from convertix.detect import detect
    from convertix.tools.catalog import available
    actions={r['target'] for r in available([detect(source)])}
    assert 'tool:crop' not in actions and 'tool:images-pdf' not in actions
    for action,params in [('crop',{'box':[0,0,10,10]}),('images-pdf',{})]:
        with pytest.raises(ConversionError):perform(action,[source],params)


@pytest.mark.parametrize('progressive',[False,True])
def test_jpeg_metadata_without_recompression(tmp_path,progressive):
    source=picture(tmp_path/'sin giro.jpg','JPEG',1)
    if progressive:
        with Image.open(source) as existing:exif=existing.info['exif']
        Image.effect_noise((700,600),50).convert('RGB').save(source,'JPEG',quality=95,exif=exif,progressive=True)
    result=perform('metadata',[source])
    with Image.open(source) as a,Image.open(result.location) as b:
        assert a.convert('RGB').tobytes()==b.convert('RGB').tobytes()
        assert a.getexif().get(34853) and not b.getexif()


@pytest.mark.parametrize('action',['resize','metadata'])
def test_apng_poster_frames_are_preserved(tmp_path,action):
    path=tmp_path/'poster.png'
    frames=[Image.new('RGBA',(80,60),c) for c in ['red','blue','green']]
    frames[0].save(path,save_all=True,append_images=frames[1:],default_image=True,duration=[80,140],loop=2)
    result=perform(action,[path],{'percent':50} if action=='resize' else {})
    with Image.open(result.location) as image:
        assert image.n_frames==3 and image.info['default_image'] and image.info['loop']==2
        for i,duration in [(1,80),(2,140)]:
            image.seek(i);image.load();assert image.info['duration']==duration


def test_animated_gif_resize_preserves_loop_and_times(tmp_path):
    path=animated(tmp_path/'animacion.gif','GIF')
    result=perform('resize',[path],{'percent':50})
    with Image.open(result.location) as image:
        assert image.n_frames==3 and image.info['loop']==2 and image.size==(40,30)
        for i,d in enumerate([80,140,210]):
            image.seek(i);assert image.info['duration']==d


def test_crop_large_resolution_uses_original_pixels(tmp_path):
    path=tmp_path/'imagen 8K.png'
    image=Image.new('RGB',(7680,4320),'blue');image.paste('red',(7000,3800,7680,4320));image.save(path)
    image.close()
    result=perform('crop',[path],{'box':[7100,3900,7600,4300]})
    with Image.open(result.location) as cropped:
        assert cropped.size==(500,400) and cropped.getpixel((250,200))==(255,0,0)
