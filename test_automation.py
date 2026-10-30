from datetime import datetime,date,timezone
from pathlib import Path
from unittest.mock import patch
import json,subprocess,tempfile,unittest
import daily_refresh as daily

class AutomationTests(unittest.TestCase):
    def test_month_boundary_and_no_duplicate(self):
        now=datetime(2026,11,2,6,37,tzinfo=timezone.utc)
        self.assertEqual(daily.expected_date(now),date(2026,11,1))
        self.assertEqual(daily.plan('2026-11-01','2026-10-31',now),'refresh')
        self.assertEqual(daily.plan('2026-11-01','2026-11-01',now),'already_current')

    def test_future_and_year_boundary_fail_closed(self):
        now=datetime(2026,11,2,6,37,tzinfo=timezone.utc)
        with self.assertRaises(ValueError):daily.plan('2026-11-02','2026-10-31',now)
        with self.assertRaises(ValueError):daily.plan('2027-01-01','2026-12-31',datetime(2027,1,2,tzinfo=timezone.utc))

    def test_failed_collection_preserves_current_even_with_apply(self):
        root=Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory(dir=root,prefix='automation-test-') as directory:
            sandbox=Path(directory).resolve();self.assertTrue(sandbox.is_relative_to(root))
            for folder in ('assets','config','data','engine','maquette'):(sandbox/folder).mkdir()
            original='{"end":"2026-10-29"}'
            (sandbox/'data/current.json').write_text(original,encoding='utf8')
            (sandbox/'verify_ui.cjs').write_text('',encoding='utf8')
            with patch.object(daily,'ROOT',sandbox),patch.object(daily,'expected_date',return_value=date(2026,10,30)),patch('sys.argv',['daily_refresh.py','--run','testfailure','--target','2026-10-30','--apply']),patch.object(daily.subprocess,'run',side_effect=subprocess.CalledProcessError(1,'simulated-failure')):
                with self.assertRaises(subprocess.CalledProcessError):daily.main()
            self.assertEqual((sandbox/'data/current.json').read_text(encoding='utf8'),original)
            result=json.loads((sandbox/'automation-artifacts/testfailure/result.json').read_text(encoding='utf8'))
            self.assertFalse(result['validated']);self.assertFalse(result['applied'])

    def test_disabled_workflow_and_worker_are_c3_only(self):
        root=Path(__file__).resolve().parent
        workflow=(root/'.github/workflows/update-daily.yml').read_text(encoding='utf8')
        self.assertNotIn('schedule:',workflow)
        self.assertIn('C3_DAILY_ENABLED',workflow)
        self.assertIn("github.repository == 'FredericP555/carburantscorse3'",workflow)
        self.assertNotIn('carburantscorse1',workflow);self.assertNotIn('carburantscorse2',workflow)
        config=(root/'cloudflare/wrangler.toml').read_text(encoding='utf8')
        self.assertIn('crons = []',config);self.assertIn('C3_ENABLED = "false"',config)

if __name__=='__main__':unittest.main()
