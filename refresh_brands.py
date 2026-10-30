"""Refresh C3-owned brand registries from official station pages, with dated changes."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
import argparse,copy,hashlib,json,sys,zipfile
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'engine/profile2'))
from scripts import resolve_new_bdr_station_brands as resolver


def refresh_registry(registry,observations,department,legacy,corrections,*,fetcher=resolver.fetch_brand,today=None,now=None):
    today=today or datetime.now(ZoneInfo('Europe/Paris')).date()
    now=now or datetime.now(timezone.utc)
    # Reuse the established resolver's selection and classification rules for
    # both territories; observations supplied to its helpers are department 13.
    rows=[dict(row,department='13') for row in observations
          if str(row.get('department'))==department
          and str(row.get('pop',''))!='A' and not row.get('is_motorway')]
    ids=resolver.observed_bdr_ids(rows)
    bounds=resolver.observed_bdr_date_bounds(rows)
    limit=20 if department=='13' else 12
    pending=resolver.ids_to_fetch(ids,legacy,registry,today=today,limit=limit)
    by_id,by_brand=resolver.load_corrections(corrections)
    result=copy.deepcopy(registry);stations=result.setdefault('stations',{})
    def fetch_one(sid):
        return sid,fetcher(sid)
    with ThreadPoolExecutor(max_workers=4) as pool:
        fetched=dict(pool.map(fetch_one,pending))
    errors={};unresolved=[]
    for sid in pending:
        old=stations.get(sid,{})
        brand,error=fetched[sid]
        if not brand:
            errors[sid]=error or 'Enseigne officielle indisponible'
            continue  # Preserve a known identity on a transient network failure.
        segment,detail,source=resolver.classify_station(sid,brand,by_id,by_brand)
        if segment=='inconnu' and brand==old.get('enseigne') and old.get('segment') in ('traditionnel','gms_lowcost'):
            segment,detail,source=old['segment'],old.get('detail','inconnu'),old.get('classification_source','confirmed_registry')
        if segment=='inconnu':
            errors[sid]='Enseigne officielle à qualifier : '+brand
            unresolved.append(sid)
            # Unlike a network failure, an official changed identity invalidates
            # the old one prospectively, even while its new category is unknown.
        first,last=bounds[sid]
        old_first=resolver._date_value(old.get('first_seen'))
        if old_first:first=min(first,old_first)
        history=copy.deepcopy(old.get('brand_history',[]))
        identity=(brand,segment,detail)
        previous=(old.get('enseigne'),old.get('segment'),old.get('detail'))
        if old.get('enseigne') and identity!=previous and (old.get('segment')!='inconnu' or brand!=old.get('enseigne')):
            valid_from=today.isoformat()
            prior=resolver._history_record(old,today-timedelta(days=1))
            if prior:prior['classification_unresolved']=old.get('classification_unresolved',False)
            if prior and prior['valid_from']<=prior['valid_to']:history.append(prior)
        else:
            valid_from=old.get('brand_valid_from') or max(date(2026,9,8),first).isoformat()
        stations[sid]={**old,'enseigne':brand,'segment':segment,'detail':detail,
                       'classification_source':source,'brand_source':'officiel',
                       'first_seen':first.isoformat(),'last_seen':last.isoformat(),
                       'verified_at':now.isoformat(),'brand_valid_from':valid_from,
                       'classification_unresolved':segment=='inconnu',
                       'brand_history':history}
    if result!=registry:result['generated_at']=now.isoformat()
    for sid in ids:
        entry=stations.get(sid,{})
        if not entry.get('enseigne') or entry.get('segment') not in ('traditionnel','gms_lowcost'):
            unresolved.append(sid)
    return result,{'observed_count':len(ids),'fetch_count':len(pending),'errors':errors,
                   'unresolved_ids':sorted(set(unresolved)),'changed':result!=registry}


def blocks_legacy_category(entry):
    # Existing historical unknown labels keep their published legacy category.
    # A newly verified unresolved change must not inherit that old category.
    return bool(entry and entry.get('classification_unresolved'))


def refresh_sources(src,out,observations,legacy):
    reports={}
    for department,name,corrections in (
        ('13','bdr_station_brands.json',ROOT/'engine/profile2/config/bdr_station_brand_corrections.csv'),
        ('20','corse_station_brands.json',ROOT/'engine/profile1/config/corse_station_brand_corrections.csv')):
        path=src/name
        registry=json.loads(path.read_text(encoding='utf8'))
        original=path.read_bytes()
        baseline_name='baseline-'+name
        (out/baseline_name).write_bytes(original)
        (src/baseline_name).write_bytes(original)
        updated,report=refresh_registry(registry,observations,department,legacy if department=='13' else {},corrections)
        raw=json.dumps(updated,ensure_ascii=False,indent=2)+'\n'
        path.write_text(raw,encoding='utf8')
        report['input_sha256']=hashlib.sha256(original).hexdigest()
        report['resolved_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        manifest_path=src/'collection.json'
        if manifest_path.exists():
            manifest=json.loads(manifest_path.read_text(encoding='utf8'))
            for asset in manifest.get('assets',[]):
                if asset.get('file')==name:asset['file']=baseline_name
            manifest.setdefault('assets',[]).append({'file':name,'sha256':report['resolved_sha256'],
                       'bytes':path.stat().st_size,'origin':'C3 official brand verification; previous registry retained as '+baseline_name})
            manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
        # ROOT is the isolated daily-refresh directory. Promotion happens only
        # after calculation and all checks succeed, never during resolution.
        (ROOT/'config'/name).write_text(raw,encoding='utf8')
        reports[department]=report
        if report['errors'] or report['unresolved_ids']:
            ids=sorted(set(report['errors'])|set(report['unresolved_ids']))
            print('::warning title=C3 enseignes à vérifier::Département '+department+' : '+', '.join(ids),flush=True)
    (out/'brand_refresh.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf8')
    return reports


def current_observations(archive,end):
    """Use the collected daily stock so closed historical IDs are not re-queried."""
    rows=[]
    with zipfile.ZipFile(archive) as bundle:
        name=next(name for name in bundle.namelist() if name.endswith('.xml'))
        with bundle.open(name) as handle:
            for _,node in ET.iterparse(handle,events=('end',)):
                if node.tag!='pdv':continue
                department='20' if node.get('cp','').startswith('20') else node.get('cp','')[:2]
                if department in ('13','20') and node.get('pop')!='A':
                    days=[price.get('maj','')[:10] for price in node.findall('prix')]
                    days=[day for day in days if day and day<=end]
                    if days:rows.append({'department':department,'station_id':node.get('id'),
                                         'date':max(days),'pop':node.get('pop'),'is_motorway':False})
                node.clear()
    return rows


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--end',required=True);args=p.parse_args()
    if not args.run.isalnum():raise ValueError('Invalid run identifier')
    src=ROOT/'sources/runs'/args.run;out=ROOT/'outputs/runs'/args.run;out.mkdir(parents=True,exist_ok=True)
    archive=src/('daily_'+date.fromisoformat(args.end).strftime('%Y%m%d')+'.zip')
    if not archive.is_file():raise ValueError('Archive quotidienne nécessaire au contrôle des enseignes : '+str(archive))
    # Keep the inherited category table authoritative, without importing its
    # entire calculation runtime into this network preparation step.
    from scripts.build_v2_production_candidate import load_bdr_categories,LEGACY_BDR
    legacy=load_bdr_categories(LEGACY_BDR)
    final_rows=current_observations(archive,args.end)
    active={(r['department'],r['station_id']) for r in final_rows}
    observations=[]
    for daily in sorted(src.glob('daily_*.zip')):
        observations.extend(row for row in current_observations(daily,args.end)
                            if (row['department'],row['station_id']) in active)
    report=refresh_sources(src,out,observations,legacy)
    print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
