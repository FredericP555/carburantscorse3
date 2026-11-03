"""Transactional C3-only refresh. The visible data changes only after every check passes."""
from pathlib import Path
from datetime import datetime,timedelta,date
from zoneinfo import ZoneInfo
import argparse,copy,json,os,shutil,subprocess,sys,tempfile
ROOT=Path(__file__).resolve().parent

def expected_date(now=None):
    return ((now or datetime.now(ZoneInfo('Europe/Paris'))).astimezone(ZoneInfo('Europe/Paris')).date()-timedelta(days=1))

def plan(target,last,now=None):
    requested=date.fromisoformat(target)
    if requested>expected_date(now):raise ValueError('La date demandée doit être au plus tard la veille à Paris')
    if requested<date(2026,10,1):raise ValueError('La date demandée précède le suivi C3')
    return 'already_current' if requested<=date.fromisoformat(last) else 'refresh'

def revalidation_seed(current,target):
    if target<='2026-10-25':raise ValueError('Le test complet doit porter sur une journée après le 25 octobre')
    result=copy.deepcopy(current)
    keep=sum(day<target for day in result['dates'])
    if keep==0:raise ValueError('No preceding history for test')
    result['dates']=result['dates'][:keep];result['end']=result['dates'][-1]
    for fuel,node in result['fuels'].items():
        for key in ('regions','gaps','e10_gaps'):
            for name,series in node.get(key,{}).items():node[key][name]=series[:keep]
        for key in ('total','total_all','eni'):
            if key in node:node[key]=node[key][:keep]
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--target');p.add_argument('--run',required=True);p.add_argument('--apply',action='store_true');a=p.parse_args()
    if not a.run.isalnum():raise ValueError('Invalid run identifier')
    target=a.target or expected_date().isoformat()
    current=json.loads((ROOT/'data/current.json').read_text(encoding='utf8'))
    revalidate=plan(target,current['end'])=='already_current'
    if revalidate and a.apply:
        print('C3 already current; nothing changed');return
    if revalidate:print('C3 full dry-run revalidation; visible history will not change')
    staging=ROOT/'.staging';staging.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='c3-',dir=staging) as directory:
        work=Path(directory).resolve();assert work.is_relative_to(staging.resolve())
        for folder in ('assets','config','data','engine','maquette'):
            shutil.copytree(ROOT/folder,work/folder,ignore=shutil.ignore_patterns('dist','C3.html','apercu.jpg','__pycache__'))
        if revalidate:
            (work/'data/current.json').write_text(json.dumps(revalidation_seed(current,target),ensure_ascii=False,indent=2),encoding='utf8')
        for file in ROOT.glob('*.py'):shutil.copyfile(file,work/file.name)
        shutil.copyfile(ROOT/'verify_ui.cjs',work/'verify_ui.cjs')
        env=dict(os.environ);env['PYTHONDONTWRITEBYTECODE']='1'
        artifacts=ROOT/'automation-artifacts'/a.run
        artifacts.mkdir(parents=True,exist_ok=True)
        validated=False
        try:
            subprocess.run([sys.executable,'-B',str(work/'run_current.py'),'--run',a.run,'--end',target,'--collect'],check=True,env=env)
            subprocess.run([sys.executable,'-B',str(work/'verify_mockup.py')],check=True,env=env)
            subprocess.run(['node',str(work/'verify_ui.cjs')],check=True,env=env)
            validated=True
        finally:
            # Keep diagnostics even when a download or validation fails.
            for folder in ('sources/runs','outputs/runs'):
                source=work/folder/a.run
                if source.exists():shutil.copytree(source,artifacts/Path(folder).parts[0],dirs_exist_ok=True)
            if validated:shutil.copyfile(work/'data/current.json',artifacts/'candidate.json')
            (artifacts/'result.json').write_text(json.dumps({'target':target,'applied':False,'validated':validated},indent=2),encoding='utf8')
        if a.apply:
            # Use only the already built, checked artifact; no fresh calculation in promotion.
            for name in ('bdr_station_brands.json','corse_station_brands.json'):
                destination=ROOT/'config'/name
                tmp=destination.with_suffix('.tmp')
                shutil.copyfile(work/'config'/name,tmp);tmp.replace(destination)
            for folder in ('maquette/dist',):
                destination=ROOT/folder;destination.mkdir(parents=True,exist_ok=True)
                for source in (work/folder).iterdir():
                    if source.is_file():
                        tmp=destination/(source.name+'.tmp');shutil.copyfile(source,tmp);tmp.replace(destination/source.name)
            tmp=ROOT/'maquette/C3.html.tmp';shutil.copyfile(work/'maquette/C3.html',tmp);tmp.replace(ROOT/'maquette/C3.html')
            tmp=ROOT/'data/current.json.tmp';shutil.copyfile(work/'data/current.json',tmp);tmp.replace(ROOT/'data/current.json')
        (artifacts/'result.json').write_text(json.dumps({'target':target,'applied':a.apply,'validated':True},indent=2),encoding='utf8')
        print('C3 validated; '+('local files updated' if a.apply else 'dry run only; visible data unchanged'))

if __name__=='__main__':main()
