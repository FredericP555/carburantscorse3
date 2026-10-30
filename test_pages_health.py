from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
import copy
import unittest

from pages_health import build_manifest, publication_needed, read_public_manifest


class PagesHealthTests(unittest.TestCase):
    def test_same_date_but_changed_presentation_requires_publication(self):
        with TemporaryDirectory(dir=Path(__file__).resolve().parent, prefix='pages-health-test-') as directory:
            root = Path(directory)
            (root / 'maquette/dist').mkdir(parents=True)
            (root / 'data').mkdir()
            (root / 'data/current.json').write_text('{"end":"2026-10-30"}')
            (root / 'maquette/dist/index.html').write_text('<html>C3</html>')
            css = root / 'maquette/dist/style.css'
            css.write_text('font-size:15px')
            original = build_manifest(root)
            self.assertFalse(publication_needed(original, copy.deepcopy(original)))
            css.write_text('font-size:18px')
            self.assertTrue(publication_needed(build_manifest(root), original))
            # The generated manifest must not recursively hash itself.
            (root / 'maquette/dist/site-manifest.json').write_text('{}')
            self.assertNotIn('site-manifest.json', build_manifest(root)['files'])

    def test_missing_or_outdated_public_data_requires_publication(self):
        expected = {'schema_version': 1, 'last_date': '2026-11-01', 'files': {'index.html': 'same'}}
        old = copy.deepcopy(expected)
        old['last_date'] = '2026-10-31'
        self.assertTrue(publication_needed(expected, old))
        self.assertTrue(publication_needed(expected, None))

    def test_404_is_missing_but_api_failure_is_not_silently_republished(self):
        expected = {'last_date': '2026-10-30'}
        def missing(request, timeout):
            self.assertEqual(timeout, 20)
            self.assertNotIn('Authorization', request.headers)
            raise HTTPError(request.full_url, 404, 'Missing', {}, None)
        self.assertIsNone(read_public_manifest(expected, missing))
        def unavailable(request, timeout):
            raise HTTPError(request.full_url, 503, 'Unavailable', {}, None)
        with self.assertRaises(HTTPError):
            read_public_manifest(expected, unavailable)

    def test_workflow_recovery_is_pages_only_and_source_is_main(self):
        root = Path(__file__).resolve().parent
        workflow = (root / '.github/workflows/static.yml').read_text(encoding='utf8')
        self.assertIn('schedule:', workflow)
        self.assertIn('pages_health.py --check', workflow)
        self.assertIn("github.ref == 'refs/heads/main'", workflow)
        self.assertNotIn('daily_refresh.py', workflow)
        self.assertNotIn('workflow_dispatches', workflow)


if __name__ == '__main__':
    unittest.main()
