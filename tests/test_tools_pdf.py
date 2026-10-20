import hashlib
from pathlib import Path
import pymupdf
import pytest
from PIL import Image
from convertix.models import ConversionError
from convertix.tools.pdf_ops import parse_pages, split_groups
from convertix.tools.service import perform


def pdf(path, count=3, *, image=False, signed=False):
    with pymupdf.open() as doc:
        for i in range(count):
            page=doc.new_page(width=300+i*20,height=400+i*10)
            page.insert_text((30,40),f'Pagina {i+1} Convertix')
            if i==1: page.set_rotation(90)
            if image:
                import io
                buffer=io.BytesIO();Image.effect_noise((1400,1800),30).convert('RGB').save(buffer,'PNG')
                page.insert_image(pymupdf.Rect(10,60,290,380),stream=buffer.getvalue())
            annotation=page.add_text_annot((20,70),'Comentario visible')
            annotation.set_info(title='Autor privado',subject='Asunto privado',creationDate='D:20260101000000')
        doc.set_toc([[1,'Inicio',1],[1,'Final',count]])
        doc.set_metadata({'author':'Autor secreto','title':'Titulo privado','creator':'Prueba','keywords':'GPS privacidad'})
        doc.set_xml_metadata('<x:xmpmeta xmlns:x="adobe:ns:meta/">secreto XMP</x:xmpmeta>')
        doc.embfile_add('adjunto.txt',b'secreto adjunto')
        if signed:
            widget=pymupdf.Widget();widget.field_name='Firma';widget.field_type=pymupdf.PDF_WIDGET_TYPE_SIGNATURE;widget.rect=pymupdf.Rect(30,100,180,140)
            doc[0].add_widget(widget)
        doc.save(path)
    return path


@pytest.mark.parametrize('count',[2,3])
def test_merge_order_dimensions_annotations_and_originals(tmp_path,count):
    paths=[pdf(tmp_path/f'documento {i} café.pdf',i+1) for i in range(count)]
    hashes=[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
    order=paths[::-1];result=perform('pdf-merge',order)
    with pymupdf.open(result.location) as doc:
        expected=[];sizes=[]
        for path in order:
            with pymupdf.open(path) as source:
                expected.extend(p.get_text() for p in source);sizes.extend(p.rect for p in source)
        assert [p.get_text() for p in doc]==expected
        assert [p.rect for p in doc]==sizes
        assert sum(len(list(p.annots() or [])) for p in doc)==sum(range(1,count+1))
        assert doc.get_toc()
    assert [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]==hashes
    second=perform('pdf-merge',order);assert second.location!=result.location
    assert not list(tmp_path.glob('.convertix-*'))


@pytest.mark.parametrize('params,expected',[
    ({'split_mode':'extract','pages':'1'},[[1]]),
    ({'split_mode':'extract','pages':'3,1'},[[3,1]]),
    ({'split_mode':'extract','pages':'1,3-4'},[[1,3,4]]),
    ({'split_mode':'each'},[[1],[2],[3],[4],[5]]),
    ({'split_mode':'interval','interval':2},[[1,2],[3,4],[5]]),
    ({'split_mode':'ranges','pages':'1-2;3;4-5'},[[1,2],[3],[4,5]])])
def test_split_modes(tmp_path,params,expected):
    source=pdf(tmp_path/'origen.pdf',5);before=source.read_bytes()
    result=perform('pdf-split',[source],params)
    assert len(result.outputs)==len(expected)
    with pymupdf.open(source) as original:
        for path,group in zip(result.outputs,expected):
            with pymupdf.open(path) as part:
                assert [p.get_text() for p in part]==[original[n-1].get_text() for n in group]
                assert [p.rect for p in part]==[original[n-1].rect for n in group]
                assert all(list(p.annots() or []) for p in part)
    assert source.read_bytes()==before
    assert result.location.is_dir()==(len(expected)>1)


@pytest.mark.parametrize('text',['','0','6','4-2','1-9','1;;2','uno','1,'])
def test_invalid_ranges(text):
    with pytest.raises(ConversionError):parse_pages(text,5)


@pytest.mark.parametrize('kind',['corrupt','protected','empty'])
def test_bad_pdf_does_not_publish(tmp_path,kind):
    bad=tmp_path/'malo.pdf'
    if kind=='corrupt':bad.write_bytes(b'%PDF-bad')
    elif kind=='empty':bad.write_bytes(b'')
    else:
        with pymupdf.open() as d:
            d.new_page();d.save(bad,encryption=pymupdf.PDF_ENCRYPT_AES_256,owner_pw='owner',user_pw='secret')
    good=pdf(tmp_path/'bueno.pdf',1)
    with pytest.raises(ConversionError):perform('pdf-merge',[good,bad])
    assert not list(tmp_path.glob('*unidos*')) and not list(tmp_path.glob('.convertix-*'))


@pytest.mark.parametrize('level',['lossless','balanced','maximum'])
def test_pdf_optimization_retains_text_and_pages(tmp_path,level):
    source=pdf(tmp_path/'pesado.pdf',2,image=True);before=source.read_bytes()
    result=perform('optimize',[source],{'level':level})
    assert result.stats['result_bytes']<result.stats['original_bytes']
    assert result.stats['saving_percent']==round((1-result.location.stat().st_size/source.stat().st_size)*100,2)
    with pymupdf.open(source) as a,pymupdf.open(result.location) as b:
        assert [p.get_text() for p in a]==[p.get_text() for p in b]
        assert [p.rect for p in a]==[p.rect for p in b]
        if level=='lossless':assert a[0].get_pixmap().samples==b[0].get_pixmap().samples
    assert source.read_bytes()==before


def test_no_reduction_requires_explicit_choice(tmp_path):
    source=tmp_path/'minimo.pdf'
    with pymupdf.open() as doc:
        doc.new_page();doc.save(source,garbage=4,deflate=True,use_objstms=1)
    with pytest.raises(ConversionError,match='No hubo reducción'):perform('optimize',[source])
    result=perform('optimize',[source],{'keep_larger':True})
    assert result.location.exists() and result.stats['saving_percent']<=0


@pytest.mark.parametrize('deep',[False,True])
def test_pdf_metadata_verified_and_visual_content_preserved(tmp_path,deep):
    source=pdf(tmp_path/'privado.pdf',2);before=source.read_bytes()
    result=perform('metadata',[source],{'metadata_mode':'deep' if deep else 'standard','remove_attachments':True})
    with pymupdf.open(source) as a,pymupdf.open(result.location) as b:
        assert not b.get_xml_metadata() and not b.metadata['author'] and not b.metadata['title']
        assert b.embfile_count()==0
        assert [p.get_text() for p in a]==[p.get_text() for p in b]
        assert [p.get_pixmap().samples for p in a]==[p.get_pixmap().samples for p in b]
        assert 'Comentario visible' in list(b[0].annots())[0].info['content']
        if deep: assert not list(b[0].annots())[0].info['title']
    assert source.read_bytes()==before and result.stats['verified_categories']


def test_signature_fields_require_explicit_acknowledgment(tmp_path):
    import re,subprocess,shutil,os
    if not shutil.which('openssl') or not shutil.which('pdfsig'):
        pytest.skip('OpenSSL y pdfsig necesarios para crear/verificar la firma sintética')
    source=pdf(tmp_path/'firmado.pdf',1,signed=True)
    # A real detached CMS signature with a disposable self-signed test certificate.
    # Keys/certificates remain in pytest's temporary folder; no personal certificates are read.
    with pymupdf.open(source) as doc:
        widget=next(doc[0].widgets())
        xref=doc.get_new_xref()
        doc.update_object(xref,'<< /Type /Sig /Filter /Adobe.PPKLite /SubFilter /adbe.pkcs7.detached /ByteRange [0 9999999999 9999999999 9999999999] /Contents <'+'0'*16384+'> >>')
        doc.xref_set_key(widget.xref,'V',f'{xref} 0 R')
        data=doc.tobytes()
    match=re.search(rb'/Contents\s*(<0{16384}>)',data);assert match
    start,end=match.span(1)
    data=data.replace(b'[0 9999999999 9999999999 9999999999]',f'[0 {start:010d} {end:010d} {len(data)-end:010d}]'.encode())
    signed_bytes=data[:start]+data[end:]
    content=tmp_path/'signed-content.bin';content.write_bytes(signed_bytes)
    key=tmp_path/'test-key.pem';cert=tmp_path/'test-cert.pem';signature=tmp_path/'signature.der'
    subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-subj','/CN=Convertix Synthetic Test/','-days','1','-keyout',str(key),'-out',str(cert)],check=True,capture_output=True)
    subprocess.run(['openssl','cms','-sign','-binary','-in',str(content),'-signer',str(cert),'-inkey',str(key),'-outform','DER','-out',str(signature),'-nosmimecap','-md','sha256'],check=True,capture_output=True)
    value=signature.read_bytes().hex().encode();assert len(value)<16384
    source.write_bytes(data[:start+1]+value+b'0'*(16384-len(value))+data[end-1:])
    env=os.environ.copy();env['HOME']=str(tmp_path)
    check=subprocess.run(['pdfsig','-nocert',str(source)],capture_output=True,text=True,env=env)
    assert 'Signature is Valid' in check.stdout,check.stdout+check.stderr
    before=source.read_bytes()
    with pytest.raises(ConversionError,match='firma'):perform('metadata',[source])
    result=perform('metadata',[source],{'allow_signed':True})
    assert result.location.exists() and source.read_bytes()==before
    after=subprocess.run(['pdfsig','-nocert',str(result.location)],capture_output=True,text=True,env=env)
    assert 'Signature is Valid' not in after.stdout  # Rewriting really does invalidate the old byte ranges.
