"""Offline boundary tests with actual inherited engines and synthetic official XMLs.

These verify archive selection and the numerical transition; they do not claim that
an official archive for a future year has already been downloaded or validated.
"""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
import csv, io, json, os, shutil, subprocess, sys, tempfile, unittest, zipfile

import collect_current
import daily_refresh
import run_current

ROOT=Path(__file__).resolve().parent


def archive_xml(year):
    days={2025:['2025-12-31'],2026:['2026-10-01','2026-12-30','2026-12-31'],2027:['2027-01-01','2027-01-02']}[year]
    stations=[]
    for sid,cp,gazole,sp95 in [('20000001','20000',2.25,1.99),('20000002','20000',2.50,2.50),('13000001','13000',1.80,1.80)]:
        rows=[]
        for day in days:
            step=.10 if day=='2027-01-02' and sid!='20000001' else 0
            rows.extend(f'<prix nom="{fuel}" id="{number}" maj="{day}T12:00:00" valeur="{value+step:.3f}"/>' for fuel,number,value in [('Gazole',1,gazole),('SP95',2,sp95)])
        stations.append(f'<pdv id="{sid}" cp="{cp}" pop="R"><adresse>Test</adresse><ville>Test</ville>'+''.join(rows)+'</pdv>')
    payload=io.BytesIO()
    with zipfile.ZipFile(payload,'w') as z:z.writestr(f'PrixCarburants_annuel_{year}.xml','<pdv_liste>'+''.join(stations)+'</pdv_liste>')
    return payload.getvalue()


class YearRolloverTests(unittest.TestCase):
    def test_archives_use_collection_year_not_target_year(self):
        self.assertEqual(collect_current.source_years(date(2026,12,31)),[2025,2026])
        self.assertEqual(collect_current.source_years(date(2027,1,1)),[2025,2026,2027])
        self.assertEqual(collect_current.source_years(date(2028,1,1)),[2025,2026,2027,2028])
        self.assertEqual(collect_current.annual_url(2026,date(2027,1,1)),'https://donnees.roulez-eco.fr/opendata/annee/2026')
        self.assertEqual(collect_current.annual_url(2027,date(2027,1,2)),'https://donnees.roulez-eco.fr/opendata/annee')
        with self.assertRaises(ValueError):collect_current.annual_url(2027,date(2026,12,31))

    def test_paris_targets_dec31_jan1_jan2_and_idempotence(self):
        for now,target,last in [(datetime(2027,1,1,6,37,tzinfo=timezone.utc),'2026-12-31','2026-12-30'),(datetime(2027,1,2,6,37,tzinfo=timezone.utc),'2027-01-01','2026-12-31'),(datetime(2027,1,3,6,37,tzinfo=timezone.utc),'2027-01-02','2027-01-01')]:
            self.assertEqual(daily_refresh.expected_date(now).isoformat(),target)
            self.assertEqual(daily_refresh.plan(target,last,now),'refresh')
            self.assertEqual(daily_refresh.plan(target,target,now),'already_current')

    def test_ufip_calibration_history_retained_when_year_changes(self):
        with patch.object(sys,'argv',['run_current.py','--run','yearcheck','--end','2027-01-02','--collect']),patch.object(run_current.subprocess,'run') as run:
            run_current.main()
        commands=[item.args[0] for item in run.call_args_list]
        ufip=next(command for command in commands if any('fetch_ufip.py' in str(part) for part in command))
        self.assertEqual(ufip[ufip.index('--start')+1],'2026-01-01')
        self.assertEqual(ufip[ufip.index('--end')+1],'2027-01-02')
        scripts=[Path(command[2]).name for command in commands]
        self.assertLess(scripts.index('refresh_brands.py'),scripts.index('run_regions.py'))
        self.assertLess(scripts.index('refresh_brands.py'),scripts.index('run_territories.py'))

    def test_actual_engines_cross_year_without_resetting_cap_phase(self):
        # The test drives run_regions itself, with real XML parsing, temporal brand
        # checks, UFIP calibration, cap detection, event extraction and daily means.
        for target in ('2026-12-31','2027-01-01','2027-01-02'):
            with self.subTest(target=target),tempfile.TemporaryDirectory(prefix='c3-year-',dir=ROOT) as directory:
                work=Path(directory)
                for name in ('collect_current.py','run_regions.py'):shutil.copyfile(ROOT/name,work/name)
                shutil.copytree(ROOT/'engine',work/'engine',ignore=shutil.ignore_patterns('__pycache__'))
                source=work/'sources/runs/boundary';source.mkdir(parents=True)
                config=work/'config';config.mkdir()
                registry={'stations':{sid:{'enseigne':brand,'segment':'traditionnel','brand_source':'fixture','brand_valid_from':'2026-09-08'} for sid,brand in [('20000001','Total'),('20000002','Vito')]}}
                for name,node in [('corse_station_brands.json',registry),('total_corse_stations.json',{'stations':{'20000001':{}}})]:
                    for folder in (source,config):(folder/name).write_text(json.dumps(node),encoding='utf8')
                for year in collect_current.source_years(date.fromisoformat(target)):(source/f'PrixCarburants_annuel_{year}.zip').write_bytes(archive_xml(year))
                dates=['2026-04-03','2026-04-06','2026-04-07','2026-05-29','2026-06-01','2026-06-02','2026-12-29','2026-12-30','2026-12-31']
                (source/'rotterdam_gazole_observed.csv').write_text('date,rotterdam_eur_l\n'+''.join(day+',1.10\n' for day in dates if day<=target),encoding='utf8')
                d=date(2026,1,1);rows=[]
                while d<=date.fromisoformat(target):rows.append(f'{d},1.10\n');d+=timedelta(days=1)
                (source/'rotterdam_gazole_daily.csv').write_text('date,rotterdam_eur_l\n'+''.join(rows),encoding='utf8')
                code="""from datetime import date
import run_regions
import bouclier_detector
class TestClock(date):
    @classmethod
    def today(cls):return date(2027,1,3)
bouclier_detector.date=TestClock
run_regions.main()
"""
                env=dict(os.environ);env['PYTHONDONTWRITEBYTECODE']='1'
                result=subprocess.run([sys.executable,'-B','-c',code,'--run','boundary','--end',target],cwd=work,env=env,text=True,capture_output=True)
                self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
                out=work/'outputs/runs/boundary'
                with (out/'regions.csv').open(encoding='utf8',newline='') as f:regions=list(csv.DictReader(f))
                current=next(row for row in regions if row['date']==target and row['region']=='corse' and row['fuel']=='Gazole')
                self.assertAlmostEqual(float(current['ttc']),2.425 if target=='2027-01-02' else 2.375)
                extraction=json.loads((out/'extraction.json').read_text(encoding='utf8'))
                self.assertEqual(extraction['max_dates']['20/Gazole'],target)
                shield=json.loads((out/'bouclier.json').read_text(encoding='utf8'))
                # Dec 30/31 confirm Jan 1 even with only one 2027 raw day.
                self.assertIn({'d1':'2026-12-30','d2':target},shield['Gazole']['ranges'])
                metadata=json.loads((work/'runtime/runs/boundary/outputs/ufip/c1_shared_meta.json').read_text(encoding='utf8'))
                self.assertEqual(metadata['rotterdam']['corsica_calibration']['entry_date'],'2026-04-08')
                self.assertTrue(all(day<=target for day in [row['date'] for row in regions]))


if __name__=='__main__':unittest.main()
