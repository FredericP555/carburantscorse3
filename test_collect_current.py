"""Official HTML/error responses must never become cached ZIP source assets."""
from pathlib import Path
from unittest.mock import Mock
import io,tempfile,unittest,zipfile
import collect_current as collect

ROOT=Path(__file__).resolve().parent


def archive(name,xml='<?xml version="1.0"?><pdv_liste/>'):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as result:result.writestr(name,xml)
    return stream.getvalue()


class CollectTests(unittest.TestCase):
    def test_html_retried_once_and_never_promoted(self):
        with tempfile.TemporaryDirectory(dir=ROOT,prefix='source-test-') as directory:
            out=Path(directory);opener=Mock(side_effect=lambda *a,**kw:io.BytesIO(b'<html>Not ready</html>'));sleep=Mock()
            with self.assertRaisesRegex(collect.OfficialArchiveError,'daily_20261030.zip'):
                collect.fetch_asset(('daily_20261030.zip','https://official.invalid'),out,opener=opener,sleeper=sleep)
            self.assertEqual(opener.call_count,2);sleep.assert_called_once_with(1)
            self.assertFalse(list(out.iterdir()))

    def test_next_attempt_valid_archive_promoted(self):
        with tempfile.TemporaryDirectory(dir=ROOT,prefix='source-test-') as directory:
            out=Path(directory);raw=archive('PrixCarburants_quotidien_20261030.xml')
            opener=Mock(side_effect=[io.BytesIO(b'<html>Not ready</html>'),io.BytesIO(raw)])
            result=collect.fetch_asset(('daily_20261030.zip','https://official.invalid'),out,opener=opener,sleeper=Mock())
            self.assertEqual((out/'daily_20261030.zip').read_bytes(),raw)
            self.assertEqual(result['bytes'],len(raw));self.assertFalse((out/'daily_20261030.tmp').exists())

    def test_wrong_annual_year_and_wrong_daily_date_rejected(self):
        with self.assertRaisesRegex(collect.OfficialArchiveError,'2026.xml'):
            collect.validate_archive(archive('PrixCarburants_annuel_2027.xml'),'PrixCarburants_annuel_2026.zip')
        with self.assertRaisesRegex(collect.OfficialArchiveError,'20261030.xml'):
            collect.validate_archive(archive('PrixCarburants_quotidien_20261029.xml'),'daily_20261030.zip')
        with self.assertRaises(collect.OfficialArchiveError):
            collect.validate_archive(archive('PrixCarburants_annuel_2026.xml','<pdv_liste><pdv>'),'PrixCarburants_annuel_2026.zip')


if __name__=='__main__':unittest.main()
