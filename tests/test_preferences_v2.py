import json

from convertix import config


def test_preferences_migrate_without_overwriting_existing_or_unknown(monkeypatch,tmp_path):
    monkeypatch.setenv('XDG_CONFIG_HOME',str(tmp_path))
    path=config.config_path();path.parent.mkdir()
    old={'theme':'light','animations':False,'notifications':False,'quality':81,'conflicts':'fail','timeout':450,'custom_future_option':'keep'}
    path.write_text(json.dumps(old))
    prefs=config.load()
    assert prefs.radial_transparency==85 and prefs.ocr_languages=='spa+eng'
    prefs.radial_transparency=100;prefs.ocr_languages='spa';config.save(prefs)
    result=json.loads(path.read_text())
    assert all(result[k]==v for k,v in old.items())
    assert result['radial_transparency']==100 and result['ocr_languages']=='spa'


def test_preferences_validate_ranges_and_ocr_input():
    p=config.Preferences.from_dict({'radial_transparency':150,'ocr_languages':'spa;$(bad)'})
    assert p.radial_transparency==100 and p.ocr_languages=='spa+eng'
