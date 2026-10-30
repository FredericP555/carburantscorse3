"""Independent regional calculation and official territory extraction for one C3 run."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'engine/profile1/scripts'),str(ROOT/'engine/profile1'),str(ROOT/'dependencies')]
import argparse, csv, gzip, hashlib, inspect, json, os, shutil, textwrap
from datetime import date
import pandas as pd

class WindowUpdates(list):
    def append(self,value):
        ts,_=value
        if ts.date()>=date(2026,10,1):super().append(value)
        elif self and self[0][0].date()<date(2026,10,1):
            if ts>=self[0][0]:self[0]=value
        else:self.insert(0,value)
class WindowDeclarations(dict):
    def setdefault(self,key,default=None):
        if key not in self:self[key]=WindowUpdates()
        return self[key]
class MaxDates(list):
    def append(self,value):
        if not self:super().append(value)
        elif value>self[0]:self[0]=value

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--end',required=True);a=p.parse_args()
    src=ROOT/'sources/runs'/a.run;out=ROOT/'outputs/runs'/a.run;out.mkdir(parents=True,exist_ok=True)
    work=ROOT/'runtime/runs'/a.run; (work/'config').mkdir(parents=True,exist_ok=True);(work/'outputs/ufip').mkdir(parents=True,exist_ok=True)
    for name in ('total_corse_stations.json','corse_station_brands.json'):shutil.copyfile(src/name,work/'config'/name)
    for name in ('rotterdam_gazole_daily.csv','rotterdam_gazole_observed.csv'):shutil.copyfile(src/name,work/'outputs/ufip'/name)
    os.chdir(work)
    import build_c1_v2_candidate as engine
    import rotterdam_corse_shared_v2 as calibration
    (work/'outputs/ufip/c1_shared_meta.json').write_text(json.dumps({'producer':'C3','rotterdam':calibration.shared_metadata()},ensure_ascii=False,indent=2),encoding='utf8')
    engine.core.download=lambda year:(src/f'PrixCarburants_annuel_{year}.zip').read_bytes()
    engine.CORSE_REGISTRY=src/'corse_station_brands.json'
    print('Detecting cap periods from current official archive',flush=True)
    shield=engine.shield_phase_v2.with_cap_phases(engine.bouclier_detector.metadata(2026))
    engine.bouclier_detector.metadata=lambda year:shield
    (out/'bouclier.json').write_text(json.dumps(shield,ensure_ascii=False,indent=2),encoding='utf8')
    source=textwrap.dedent(inspect.getsource(engine.build_v2_daily)).replace('declarations: dict = {}','declarations: dict = _WindowDeclarations()').replace('source_dates: list[date] = []','source_dates: list[date] = _MaxDates()')
    anchor='                reasons[f"{region_kind}/{fuel}/{decision.reason}"] += 1'
    assert source.count(anchor)==1
    source=source.replace(anchor,anchor+'\n                _trace.append((sid,region,fuel,day,last_price,last_ts,decision.eligible,decision.reason))')
    trace=[];engine.__dict__.update(_WindowDeclarations=WindowDeclarations,_MaxDates=MaxDates,_trace=trace)
    exec(compile(source,'<C3 regional trace>','exec'),engine.__dict__)
    print('Calculating regional series',flush=True)
    df,audit=engine.build_v2_daily([2025,2026],date(2026,10,1),date.fromisoformat(a.end))
    df.to_csv(out/'regions.csv',index=False)
    pd.DataFrame(trace,columns=['station_id','region','fuel','date','price','source_timestamp','eligible','reason']).to_csv(out/'regional_stations.csv.gz',index=False,compression='gzip')
    (out/'regional_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
    print('Extracting official declarations and rupture/closure events',flush=True)
    import export_shared_c2_snapshot as export
    events=[];count=0;max_dates={}
    with gzip.open(out/'observations.csv.gz','wt',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=export.FIELDS);w.writeheader()
        for year in (2025,2026):
            for row in export.iter_rows(year,event_sink=events):
                if row['date']>a.end:continue
                w.writerow(row);count+=1
                key=row['department']+'/'+row['fuel'];max_dates[key]=max(max_dates.get(key,''),row['date'])
    with gzip.open(out/'events.csv.gz','wt',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=export.EVENT_FIELDS);w.writeheader();w.writerows(events)
    (out/'extraction.json').write_text(json.dumps({'rows':count,'max_dates':max_dates,'events':len(events),'end':a.end},indent=2),encoding='utf8')
    print('Regional calculation and extraction complete',flush=True)

if __name__=='__main__':main()
