"""C3 territory engine: only C3-owned code, inputs, registry and output paths."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'engine/profile2'),str(ROOT/'dependencies')]
import argparse,csv,gzip,json,os,inspect,textwrap
from datetime import date
import pandas as pd

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--end',required=True);a=p.parse_args()
    src=ROOT/'sources/runs'/a.run;out=ROOT/'outputs/runs'/a.run
    os.chdir(ROOT/'runtime/runs'/a.run)
    from scripts import build_v2_production_candidate as engine
    from scripts.v2_event_guards import EventGuards
    from carburantscorse2.publication import build_publication_state,build_gap_series,unknown_recent_bdr_stations
    engine.BDR_REGISTRY=src/'bdr_station_brands.json'
    with gzip.open(out/'observations.csv.gz','rt',encoding='utf8') as f:obs=list(csv.DictReader(f))
    for row in obs:
        row['is_motorway']=str(row['is_motorway']).lower() in ('true','1','yes')
        row['price']=float(row['price']) if row.get('price') else None
    with gzip.open(out/'events.csv.gz','rt',encoding='utf8') as f:events=list(csv.DictReader(f))
    guards=EventGuards(events,release_tag='C3-'+a.run,metadata={});guards.bind_observations(obs)
    legacy=engine.load_bdr_categories(engine.LEGACY_BDR)
    brand_refresh=json.loads((out/'brand_refresh.json').read_text(encoding='utf8'))
    registry=engine.load_registry(engine.BDR_REGISTRY)
    from scripts.resolve_new_bdr_station_brands import _entry_for_day
    from refresh_brands import blocks_legacy_category
    category=engine._bdr_category_resolver(legacy,registry)
    def verified_category(station_id,day):
        entry=_entry_for_day(registry['stations'].get(str(station_id)),pd.Timestamp(day).date())
        if blocks_legacy_category(entry):return None
        return category(station_id,day)
    state=build_publication_state(pd.DataFrame(obs),global_end=pd.Timestamp(a.end),bdr_category_resolver=verified_category)
    state=state[state.date>=pd.Timestamp('2026-10-01')].copy()
    code=textwrap.dedent(inspect.getsource(engine._evaluate_v2));anchor='        eligible.append(bool(decision.eligible));';assert code.count(anchor)==1
    code=code.replace(anchor,'        _trace.append(decision.reason)\n'+anchor);reasons=[];engine.__dict__['_trace']=reasons
    exec(compile(code,'<C3 territorial trace>','exec'),engine.__dict__)
    corse=json.loads((src/'corse_station_brands.json').read_text(encoding='utf8'))['stations']
    shield=json.loads((out/'bouclier.json').read_text(encoding='utf8'))
    print('Calculating territorial decisions',flush=True)
    state,audit=engine._evaluate_v2(state,bouclier=shield,event_guards=guards,corse_stations=corse,start=date(2026,10,1),end=date.fromisoformat(a.end));state['reason']=reasons
    from scripts.resolve_new_bdr_station_brands import _entry_for_day
    from a4c_common.corse_brand import registry_entry_for_date
    brands=[];segments=[]
    for r in state.itertuples():
        d=pd.Timestamp(r.date).date();entry=registry_entry_for_date(corse.get(str(r.station_id)),d) if str(r.department)=='20' else _entry_for_day(registry['stations'].get(str(r.station_id)),d)
        brands.append((entry or {}).get('enseigne',''));segments.append((entry or {}).get('segment','inconnu'))
    state['brand']=brands;state['brand_segment']=segments
    unknown=unknown_recent_bdr_stations(state,since=pd.Timestamp('2026-10-26'))
    gaps={}
    for cf,bf,key in [('Gazole','Gazole','gazole'),('SP95','SP95','sp95'),('SP95','E10','e10')]:
        gaps[key]={scope:build_gap_series(state,corsica_fuel=cf,bdr_fuel=bf,bdr_scope=scope,include_levels=True) for scope in ('all','network')}
    state.to_csv(out/'territorial_stations.csv.gz',index=False,compression='gzip')
    (out/'gaps.json').write_text(json.dumps(gaps,ensure_ascii=False,indent=2),encoding='utf8')
    (out/'territorial_audit.json').write_text(json.dumps({'engine':audit,'events':guards.audit(),'unknown_new_bdr':unknown,'brand_refresh':brand_refresh},ensure_ascii=False,indent=2),encoding='utf8')
    print('Territorial calculation complete; unknown new BdR: '+str(unknown),flush=True)

if __name__=='__main__':main()
