"""Manual, independent C3 refresh. No deployment, scheduling or upstream writes."""
from pathlib import Path
import argparse,os,subprocess,sys
ROOT=Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--end',required=True);p.add_argument('--collect',action='store_true');a=p.parse_args()
    env=dict(os.environ);env['PYTHONPATH']=str(ROOT/'dependencies');env['PYTHONDONTWRITEBYTECODE']='1'
    def run(script,*args):
        subprocess.run([sys.executable,'-B',str(ROOT/script),*args],env=env,check=True)
    if a.collect:
        run('collect_current.py','--run',a.run,'--end',a.end)
        run('engine/profile1/scripts/fetch_ufip.py','--end',a.end,'--output-dir',str(ROOT/'sources/runs'/a.run),'--attempts','2','--retry-delay','1')
    for script in ('run_regions.py','run_territories.py','assemble_current.py'):
        run(script,'--run',a.run,'--end',a.end)
    run('build_mockup.py')
    run('test_current.py')

if __name__=='__main__':main()
