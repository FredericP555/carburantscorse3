"""Verify the standalone artifact equals the checked C3-owned dataset."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parent
raw=(ROOT/'maquette/dist/data.js').read_text(encoding='utf8')
d=json.loads(raw.removeprefix('window.C3_DATA = ').strip().removesuffix(';'))
source=ROOT/'data/current.json'
if not source.exists():source=ROOT/'data/history_20261025.json'
assert d==json.loads(source.read_text(encoding='utf8'))
html=(ROOT/'maquette/C3.html').read_text(encoding='utf8')
assert '<script src=' not in html and 'href="style.css"' not in html
assert 'TTC ÷ 1,13' in html and 'TTC ÷ 1,20' in html
assert 'sans Access, low cost ni Élan' in html
assert d['end'] in html
result={'first_date':d['start'],'last_date':d['end'],'days':len(d['dates']),'standalone_data_matches_checked_dataset':True,'standalone_html':True,'deployment':False,'upstream_changes':False}
(ROOT/'maquette/verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(result,ensure_ascii=False,indent=2))
