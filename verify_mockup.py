"""Verify the standalone artifact equals the checked C3-owned dataset."""
from pathlib import Path
from html.parser import HTMLParser
import hashlib,json,re
ROOT=Path(__file__).resolve().parent
raw=(ROOT/'maquette/dist/data.js').read_text(encoding='utf8')
d=json.loads(raw.removeprefix('window.C3_DATA = ').strip().removesuffix(';'))
source=ROOT/'data/current.json'
if not source.exists():source=ROOT/'data/history_20261025.json'
assert d==json.loads(source.read_text(encoding='utf8'))
html=(ROOT/'maquette/dist/C3.html').read_text(encoding='utf8')
assert '<script src=' not in html and 'href="style.css"' not in html
assert 'TTC ÷ 1,13' in html and 'TTC ÷ 1,20' in html
assert 'data-total-scope="all" aria-pressed="true"' in html
assert 'data-total-scope="traditional" aria-pressed="false"' in html
assert 'hors Access, autoroutes et Élan' in html
assert 'id="total-access-note"' in html and 'réseau à prix bas de TotalEnergies' in html
assert d['end'] in html
assert raw.strip().replace('</script','<\\/script') in html
page=(ROOT/'maquette/dist/index.html').read_text(encoding='utf8')
for name in ('style.css','chart.min.js','data.js','app.js'):
    digest=hashlib.sha256((ROOT/'maquette/dist'/name).read_bytes()).hexdigest()[:12]
    assert f'"{name}?v={digest}"' in page, f'Missing asset version: {name}'
assert not re.search(r'\{\{[A-Z_]+\}\}',page)

class PublicLinks(HTMLParser):
    def handle_starttag(self,tag,attrs):
        if tag=='a':
            href=dict(attrs).get('href','')
            assert 'github.com' not in href.casefold(), 'Unexpected public GitHub link'

for artifact in (page,html):
    PublicLinks().feed(artifact)
    assert 'MAQUETTE LOCALE' not in artifact
    assert 'La mise à jour automatique n’est pas encore activée' not in artifact
    assert 'Maquette de discussion' not in artifact
    assert 'Dernière journée disponible' in artifact
result={'first_date':d['start'],'last_date':d['end'],'days':len(d['dates']),'standalone_data_matches_checked_dataset':True,'standalone_html':True,'deployment':False,'upstream_changes':False}
(ROOT/'maquette/verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(result,ensure_ascii=False,indent=2))
