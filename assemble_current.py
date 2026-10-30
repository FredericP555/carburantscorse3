"""Validate a C3 run and append new dates, preserving all existing historical points."""
from pathlib import Path
import argparse,copy,hashlib,json,re
from datetime import date,timedelta
import pandas as pd
ROOT=Path(__file__).resolve().parent

def total(entry):
    name=re.sub('[^a-z0-9]','',str(entry).casefold())
    return name in {'total','totalenergies','totalcontact','totalenergiescontact'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--end',required=True);a=p.parse_args()
    out=ROOT/'outputs/runs'/a.run;src=ROOT/'sources/runs'/a.run
    path=ROOT/'data/current.json';seed=path if path.exists() else ROOT/'data/history_20261025.json'
    old=json.loads(seed.read_text(encoding='utf8'));data=copy.deepcopy(old)
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
    extraction=json.loads((out/'extraction.json').read_text(encoding='utf8'))
    for key in ('13/Gazole','13/SP95','13/E10','20/Gazole','20/SP95'):
        assert extraction['max_dates'].get(key,'')>=a.end, 'Source incomplète : '+key
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
            t=good[(good.date==day)&good.fuel.eq(fuel)&good.brand_segment.eq('traditionnel')&good.brand.map(total)]
            c=t[t.department.eq('20')];b=t[t.department.eq('13')]
            assert len(c)>0 and len(b)>0
            unknown=good[(good.date==day)&good.fuel.eq(fuel)&good.brand.fillna('').eq('')&good.category.ne('gms')]
            current['total'].append({'date':day,'diagnostic':round(100*(c.price_ht.mean()-b.price_ht.mean()),2),'validated_gap':None,'n_corse':len(c),'n_bdr':len(b),'unresolved_ids':sorted(unknown.station_id.unique().tolist()),'status':'diagnostic'})
            if fuel=='Gazole':
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
        for region in data['fuels'][fuel]['regions']:assert data['fuels'][fuel]['regions'][region][:len(old['dates'])]==old['fuels'][fuel]['regions'][region]
        for scope in ('all','reseau'):assert data['fuels'][fuel]['gaps'][scope][:len(old['dates'])]==old['fuels'][fuel]['gaps'][scope]
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
