from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from convertix.service import convert


def metadata(path):
    with Image.open(path) as im:
        loop=im.info.get('loop');frames=[];durations=[]
        for i in range(im.n_frames):
            im.seek(i);im.load();durations.append(im.info['duration']);frames.append(im.convert('RGBA').copy())
        return loop,durations,frames


@pytest.mark.parametrize('loop',[None,0,2])
def test_animation_roundtrip_duration_alpha_and_repetitions(tmp_path,loop):
    frames=[]
    for x in (4,18,32):
        frame=Image.new('RGBA',(64,48),(0,0,0,0))
        ImageDraw.Draw(frame).rectangle((x,10,x+15,30),fill=(200,30,80,255));frames.append(frame)
    source=tmp_path/'animación original.gif'
    frames[0].save(source,save_all=True,append_images=frames[1:],duration=[80,140,210],disposal=2,**({} if loop is None else {'loop':loop}))
    before=source.read_bytes()
    webp=convert(source,'webp').outputs[0]
    output=convert(webp,'gif').outputs[0]
    a=metadata(source);b=metadata(webp);c=metadata(output)
    assert a[1]==b[1]==c[1]==[80,140,210]
    assert b[0]==(1 if loop is None else 0 if loop==0 else loop+1)
    assert c[0]==loop
    for left,right in zip(a[2],b[2]):
        assert left.getchannel('A').tobytes()==right.getchannel('A').tobytes()
    for left,right in zip(a[2],c[2]):
        assert left.getchannel('A').tobytes()==right.getchannel('A').tobytes()
    assert source.read_bytes()==before
