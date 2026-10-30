"""Collect immutable official inputs for C3; no calls that mutate C1/C2."""
from pathlib import Path
from datetime import datetime, timezone, date, timedelta
from concurrent.futures import ThreadPoolExecutor
import argparse, hashlib, io, json, re, shutil, time, urllib.error, urllib.request, zipfile, zlib
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parent
HISTORY_START=date(2026,10,1)
FIRST_SOURCE_YEAR=2025


class OfficialArchiveError(RuntimeError):
    """A required official asset is not yet available or fails its input contract."""


def validate_archive(raw,name):
    annual=re.fullmatch(r'PrixCarburants_annuel_(\d{4})\.zip',name)
    daily=re.fullmatch(r'daily_(\d{8})\.zip',name)
    expected=f'PrixCarburants_annuel_{annual[1]}.xml' if annual else f'PrixCarburants_quotidien_{daily[1]}.xml' if daily else None
    try:
        if not raw.startswith(b'PK'):
            raise ValueError('réponse non ZIP (page HTML ou archive non encore disponible)')
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            members=[member for member in archive.namelist() if member.rsplit('/',1)[-1]==expected]
            if expected is None or len(members)!=1:
                raise ValueError(f'XML attendu absent : {expected}')
            with archive.open(members[0]) as source:
                first=True
                for event,element in ET.iterparse(source,events=('start','end')):
                    if first:
                        first=False
                        if element.tag.rsplit('}',1)[-1]!='pdv_liste':
                            raise ValueError('le XML ne contient pas la liste officielle des points de vente')
                    if event=='end':element.clear()
                if first:raise ValueError('le XML est vide')
    except (ValueError,zipfile.BadZipFile,ET.ParseError,RuntimeError,EOFError,zlib.error) as exc:
        raise OfficialArchiveError(f'Archive officielle indisponible ou invalide : {name} — {exc}') from exc


def fetch_asset(item,out,*,opener=None,sleeper=None,attempts=2):
    """Validate before publishing the cached filename; retry one transient failure."""
    if attempts not in (1,2):raise ValueError('Une ou deux tentatives de collecte sont autorisées')
    opener=opener or urllib.request.urlopen;sleeper=sleeper or time.sleep
    name,url=item;target=out/name
    raw=target.read_bytes() if target.exists() else None
    if raw is not None:
        validate_archive(raw,name)
    else:
        for attempt in range(1,attempts+1):
            try:
                print(f'Downloading {name} (attempt {attempt}/{attempts})',flush=True)
                req=urllib.request.Request(url,headers={'User-Agent':'A4C-C3/1.0'})
                with opener(req,timeout=90) as response:raw=response.read()
                validate_archive(raw,name)
                tmp=target.with_suffix('.tmp');tmp.write_bytes(raw);tmp.replace(target)
                break
            except (urllib.error.URLError,TimeoutError,OfficialArchiveError) as exc:
                if attempt==attempts:
                    raise OfficialArchiveError(f'Archive officielle indisponible ou invalide : {name} après {attempts} tentative(s) — {exc}') from exc
                sleeper(1)
    return {'file':name,'url':url,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}


def source_years(end):
    """Keep the complete C3 history and the previous-year opening station state."""
    if end < HISTORY_START:
        raise ValueError('La collecte doit couvrir le suivi depuis le 1er octobre 2026')
    return list(range(FIRST_SOURCE_YEAR,end.year+1))


def annual_url(year,collected_on=None):
    """The unqualified endpoint changes year on Jan 1, including for a Dec 31 run."""
    collected_on=collected_on or datetime.now(ZoneInfo('Europe/Paris')).date()
    if year>collected_on.year:
        raise ValueError('Une archive annuelle future ne peut pas être collectée')
    suffix='' if year==collected_on.year else f'/{year}'
    return 'https://donnees.roulez-eco.fr/opendata/annee'+suffix

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--end',default='2026-10-29');a=p.parse_args()
    end=date.fromisoformat(a.end);years=source_years(end)
    assert a.run.isalnum(), 'run must be an alphanumeric identifier'
    out=ROOT/'sources'/'runs'/a.run;out.mkdir(parents=True,exist_ok=True)
    collected_on=datetime.now(ZoneInfo('Europe/Paris')).date()
    items=[(f'PrixCarburants_annuel_{year}.zip',annual_url(year,collected_on)) for year in years]
    current=ROOT/'data/current.json'
    last=date.fromisoformat(json.loads(current.read_text(encoding='utf8'))['end']) if current.exists() else date(2026,10,25)
    days=[last+timedelta(days=i) for i in range(1,(end-last).days+1)]
    items += [(f'daily_{d:%Y%m%d}.zip',f'https://donnees.roulez-eco.fr/opendata/jour/{d:%Y%m%d}') for d in days]
    with ThreadPoolExecutor(max_workers=3) as pool:assets=list(pool.map(lambda item:fetch_asset(item,out),items))
    for name in ('bdr_station_brands.json','corse_station_brands.json','total_corse_stations.json'):
        shutil.copyfile(ROOT/'config'/name,out/name)
    assets += [{'file':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in out.glob('*.json') if p.name!='collection.json']
    (out/'collection.json').write_text(json.dumps({'collected_at':datetime.now(timezone.utc).isoformat(),'assets':assets},indent=2),encoding='utf8')
    print('Collection saved: '+str(out),flush=True)

if __name__=='__main__':main()
