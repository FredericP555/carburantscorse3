"""Collect immutable official inputs for C3; no calls that mutate C1/C2."""
from pathlib import Path
from datetime import datetime, timezone, date, timedelta
from concurrent.futures import ThreadPoolExecutor
import argparse, hashlib, json, shutil, urllib.request, zipfile

ROOT=Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--end',default='2026-10-29');a=p.parse_args()
    end=date.fromisoformat(a.end);assert end.year==2026, 'Le passage à 2027 nécessite une validation des règles annuelles'
    assert a.run.isalnum(), 'run must be an alphanumeric identifier'
    out=ROOT/'sources'/'runs'/a.run;out.mkdir(parents=True,exist_ok=True)
    def fetch(item):
        name,url=item;target=out/name
        if not target.exists():
            print('Downloading '+name,flush=True)
            req=urllib.request.Request(url,headers={'User-Agent':'A4C-C3/1.0'})
            with urllib.request.urlopen(req,timeout=90) as r:raw=r.read()
            tmp=target.with_suffix('.tmp');tmp.write_bytes(raw);tmp.replace(target)
        if target.suffix=='.zip':
            with zipfile.ZipFile(target) as z:
                assert any(n.endswith('.xml') for n in z.namelist()),name
        return {'file':name,'url':url,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'bytes':target.stat().st_size}
    items=[('PrixCarburants_annuel_2026.zip','https://donnees.roulez-eco.fr/opendata/annee')]
    current=ROOT/'data/current.json'
    last=date.fromisoformat(json.loads(current.read_text(encoding='utf8'))['end']) if current.exists() else date(2026,10,25)
    days=[last+timedelta(days=i) for i in range(1,(end-last).days+1)]
    items += [(f'daily_{d:%Y%m%d}.zip',f'https://donnees.roulez-eco.fr/opendata/jour/{d:%Y%m%d}') for d in days]
    with ThreadPoolExecutor(max_workers=3) as pool:assets=list(pool.map(fetch,items))
    old=ROOT/'sources'/'PrixCarburants_annuel_2025.zip'
    if old.exists():shutil.copyfile(old,out/old.name)
    else:assets.append(fetch((old.name,'https://donnees.roulez-eco.fr/opendata/annee/2025')))
    for name in ('bdr_station_brands.json','corse_station_brands.json','total_corse_stations.json'):
        shutil.copyfile(ROOT/'config'/name,out/name)
    assets += [{'file':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in out.glob('*.json') if p.name!='collection.json']
    assets.append({'file':old.name,'sha256':hashlib.sha256((out/old.name).read_bytes()).hexdigest(),'origin':'previous immutable official download'})
    (out/'collection.json').write_text(json.dumps({'collected_at':datetime.now(timezone.utc).isoformat(),'assets':assets},indent=2),encoding='utf8')
    print('Collection saved: '+str(out),flush=True)

if __name__=='__main__':main()
