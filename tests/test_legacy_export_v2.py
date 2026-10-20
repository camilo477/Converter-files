import zipfile

import pytest

from convertix.models import ConversionError
from convertix.service import convert


@pytest.mark.integration
@pytest.mark.parametrize('origin,target,modern',[('odt','doc','docx'),('ods','xls','xlsx'),('odp','ppt','pptx')])
def test_legacy_exports_keep_content_after_roundtrip(samples,tmp_path,origin,target,modern):
    import shutil
    source=tmp_path/('antiguo.'+origin);shutil.copyfile(samples[origin],source);before=source.read_bytes()
    legacy=convert(source,target).outputs[0]
    roundtrip=convert(legacy,modern).outputs[0]
    with zipfile.ZipFile(roundtrip) as z:
        texts=' '.join(z.read(name).decode('utf-8') for name in z.namelist() if name.endswith('.xml'))
        assert 'Convertix' in texts
        assert ('42' if origin=='ods' else '123') in texts
    assert source.read_bytes()==before


def test_xls_refuses_data_beyond_legacy_capacity(tmp_path):
    openpyxl=pytest.importorskip('openpyxl')
    book=openpyxl.Workbook();book.active['A65537']='No perder este dato'
    source=tmp_path/'límite.xlsx';book.save(source)
    with pytest.raises(ConversionError,match='65 536'):
        convert(source,'xls')
    assert not list(tmp_path.glob('*.xls'))
