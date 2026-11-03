"""Validate a C3 run and append new dates, preserving all existing historical points."""
from pathlib import Path
import argparse,copy,hashlib,json,re
from datetime import date,timedelta
import pandas as pd
from source_coverage import validate_source_coverage
ROOT=Path(__file__).resolve().parent

def total(entry):
    name=re.sub('[^a-z0-9]','',str(entry).casefold())
    return name in {'total','totalenergies','totalcontact','totalenergiescontact'}

def total_with_access(entry):
    name=re.sub('[^a-z0-9]','',str(entry).casefold())
    return total(entry) or name in {'totalaccess','totalenergiesaccess'}


def total_point(good,day,fuel,*,include_access=False):
    day_rows=good[(good.date==day)&good.fuel.eq(fuel)]
    traditional=day_rows[day_rows.brand_segment.eq('traditionnel')&day_rows.brand.map(total).astype(bool)]
    # The Corsica population is identical in both comparisons. Only BDR expands.
    c=traditional[traditional.department.eq('20')]
    b=(day_rows[day_rows.department.eq('13')&day_rows.brand.map(total_with_access).astype(bool)]
       if include_access else traditional[traditional.department.eq('13')])
    available=len(c)>0 and len(b)>0
    # Only Gazole is displayed in the brand comparison. The retired SP95
    # diagnostic must not prevent publication of the other, available series.
    if fuel=='Gazole' and not available:
        raise ValueError('Comparaison Total gazole indisponible : '+day)
    unknown=good[(good.date==day)&good.fuel.eq(fuel)&good.brand.fillna('').eq('')&good.category.ne('gms')]
    return {'date':day,'diagnostic':round(100*(c.price_ht.mean()-b.price_ht.mean()),2) if available else None,
            'validated_gap':None,'n_corse':len(c),'n_bdr':len(b),
            'unresolved_ids':sorted(unknown.station_id.unique().tolist()),
            'status':'diagnostic' if available else 'unavailable'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--end',required=True);a=p.parse_args()
    out=ROOT/'outputs/runs'/a.run;src=ROOT/'sources/runs'/a.run
    path=ROOT/'data/current.json';seed=path if path.exists() else ROOT/'data/history_20261025.json'
    old=json.loads(seed.read_text(encoding='utf8'));data=copy.deepcopy(old)
    (out/'baseline.json').write_text(json.dumps(old,ensure_ascii=False,indent=2),encoding='utf8')
    start=date.fromisoformat(old['end'])+timedelta(days=1);end=date.fromisoformat(a.end)
    assert end>=date.fromisoformat(old['end'])
    days=[(start+timedelta(days=i)).isoformat() for i in range(max(0,(end-start).days+1))]
    regional=pd.read_csv(out/'regions.csv');s=pd.read_csv(out/'territorial_stations.csv.gz',dtype={'department':str,'station_id':str})
    assert not s.duplicated(['date','station_id','fuel']).any()
    assert not s['pop'].eq('A').any(),'Motorway row in calculation state'
    good=s[s.eligible_publication];assert good.price.between(1.10,3.00).all()
    gaps=json.loads((out/'gaps.json').read_text(encoding='utf8'))
    audit=json.loads((out/'territorial_audit.json').read_text(encoding='utf8'))
    assert not audit['unknown_new_bdr']
    assert not audit['engine'].get('r2_errors'),audit['engine'].get('r2_errors')
    assert not audit['engine'].get('r2_unavailable'), 'R2 unavailable'
    coverage=validate_source_coverage(src,out/'observations.csv.gz',days)
    (out/'source_coverage.json').write_text(json.dumps(coverage,ensure_ascii=False,indent=2),encoding='utf8')
    levels=[];comparisons=[]
    for fuel in ('Gazole','SP95'):
        current=data['fuels'][fuel];key='gazole' if fuel=='Gazole' else 'sp95'
        for region,values in current['regions'].items():
            name='corse' if region=='Corse' else region
            series=regional[(regional.fuel==fuel)&regional.region.eq(name)].set_index('date')
            for day in days:
                assert day in series.index,(fuel,region,day)
                values.append(round(float(series.loc[day,'ttc'])+1e-12,3))
        for scope,source_scope in [('all','all'),('reseau','network')]:
            rows={r['date']:r['ecart'] for r in gaps[key][source_scope]}
            for day in days:current['gaps'][scope].append(rows[day])
            if fuel=='SP95':
                rows={r['date']:r['ecart'] for r in gaps['e10'][source_scope]}
                for day in days:current['e10_gaps'][scope].append(rows[day])
        for day in days:
            current['total'].append(total_point(good,day,fuel))
            if fuel=='Gazole':
                current['total_all'].append(total_point(good,day,fuel,include_access=True))
                e=good[(good.date==day)&good.fuel.eq(fuel)&good.brand_segment.eq('traditionnel')&good.brand.fillna('').str.casefold().eq('eni')]
                ec=e[e.department.eq('20')];eb=e[e.department.eq('13')];assert len(ec)>0 and len(eb)>0
                current['eni'].append({'date':day,'gap':round(100*(ec.price_ht.mean()-eb.price_ht.mean()),2),'n_corse':len(ec),'n_bdr':len(eb)})
        # Keep all historical comparisons against the new-input replay visible in the audit.
        for scope,source_scope in [('all','all'),('reseau','network')]:
            rows={r['date']:r['ecart'] for r in gaps[key][source_scope]}
            for i,day in enumerate(old['dates']):
                comparisons.append({'date':day,'fuel':fuel,'scope':scope,'preserved':old['fuels'][fuel]['gaps'][scope][i],'replay':rows.get(day)})
    data['dates']+=days;data['end']=a.end
    for fuel in data['fuels']:
        for group in ('regions','gaps','e10_gaps'):
            for name,values in old['fuels'][fuel].get(group,{}).items():
                assert data['fuels'][fuel][group][name][:len(old['dates'])]==values
        for group in ('total','total_all','eni'):
            if group in old['fuels'][fuel]:assert data['fuels'][fuel][group][:len(old['dates'])]==old['fuels'][fuel][group]
    data['provenance']['last_run']=a.run;data['provenance']['new_days']='Independent C3 annual official archive calculation; historical seed preserved'
    # Station-level audit tables make filtering and coverage reviewable.
    s.groupby(['date','fuel','department','eligible_publication','reason']).size().reset_index(name='stations').to_csv(out/'exclusions.csv',index=False)
    good.groupby(['date','fuel','department','category']).size().reset_index(name='stations').to_csv(out/'coverage.csv',index=False)
    tg=s[s.fuel.eq('Gazole')&s.brand.map(total)&s.brand_segment.eq('traditionnel')&s.department.eq('13')]
    tg.groupby(['date','eligible_publication','reason']).size().reset_index(name='stations').to_csv(out/'total_bdr_exclusions.csv',index=False)
    tg.to_csv(out/'total_bdr_station_audit.csv',index=False)
    pd.DataFrame(comparisons).to_csv(out/'historical_replay_comparison.csv',index=False)
    # Compare the values actually displayed to the independent replay without rewriting the seed.
    rd=[]
    for fuel,v in old['fuels'].items():
        for name,prices in v['regions'].items():
            reg='corse' if name=='Corse' else name
            by=regional[regional.fuel.eq(fuel)&regional.region.eq(reg)].set_index('date').ttc.to_dict()
            for day,price in zip(old['dates'],prices):rd.append({'date':day,'fuel':fuel,'region':name,'preserved':price,'replay':round(float(by[day])+1e-12,3)})
    pd.DataFrame(rd).to_csv(out/'historical_regions_comparison.csv',index=False)
    source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in src.iterdir() if p.is_file()}
    result={'run':a.run,'end':a.end,'added_dates':days,'historical_points_preserved':True,'motorway_excluded':True,'unknown_new_bdr':[], 'source_hashes':source_hashes,'r2_errors':audit['engine'].get('r2_errors',{}),'status':'local_only'}
    data['run_checks']=result
    (out/'candidate.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8');tmp.replace(path)
    (out/'checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k!='source_hashes'},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
