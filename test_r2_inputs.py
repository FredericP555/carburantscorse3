"""Immutable UFIP inputs are read once per run, never carried into another run."""
from pathlib import Path
from types import SimpleNamespace
import json,os,tempfile,unittest
from run_territories import cache_r2_inputs

ROOT=Path(__file__).resolve().parent


class R2InputTests(unittest.TestCase):
    def test_canonical_paths_cached_and_new_run_reads_new_inputs(self):
        with tempfile.TemporaryDirectory(dir=ROOT,prefix='r2-input-test-') as directory:
            root=Path(directory);calls=[]
            def make_reader(name):
                def read(path=root/name):
                    calls.append(str(path));return json.loads(Path(path).read_text(encoding='utf8'))
                return read
            readers={name:make_reader(name+'.json') for name in ('read_daily_values','read_observed_csv','corsica_from_shared_metadata')}
            module=SimpleNamespace(**readers)
            for name in readers:(root/(name+'.json')).write_text('{"value":1}',encoding='utf8')
            cache_r2_inputs(module)
            self.assertEqual(len(calls),3)
            old=os.getcwd()
            try:
                os.chdir(root)
                for name in readers:
                    for _ in range(100):self.assertEqual(getattr(module,name)(Path(name+'.json')),{'value':1})
                self.assertEqual(len(calls),3)
                # A later run reusing this interpreter and these filenames must
                # load the new bytes, rather than reuse the previous run's data.
                for name in readers:(root/(name+'.json')).write_text('{"value":2}',encoding='utf8')
                cache_r2_inputs(module)
                for name in readers:self.assertEqual(getattr(module,name)(),{'value':2})
                self.assertEqual(len(calls),6)
            finally:os.chdir(old)


if __name__=='__main__':unittest.main()
