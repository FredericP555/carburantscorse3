"""Compare the checked-in C3 site with its public artifact; never change upstream data."""
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import argparse
import hashlib
import json
import os

ROOT = Path(__file__).resolve().parent
PUBLIC_MANIFEST = 'https://fredericp555.github.io/carburantscorse3/site-manifest.json'
MANIFEST_NAME = 'site-manifest.json'


def build_manifest(root=ROOT):
    site = root / 'maquette/dist'
    if not (site / 'index.html').is_file():
        raise ValueError('Missing C3 index.html')
    files = {}
    for path in sorted(site.rglob('*')):
        if path.is_symlink():
            raise ValueError('Symlinks are not allowed in the C3 Pages artifact')
        if path.is_file() and path.relative_to(site).as_posix() != MANIFEST_NAME:
            files[path.relative_to(site).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    data = json.loads((root / 'data/current.json').read_text(encoding='utf8'))
    return {'schema_version': 1, 'last_date': data['end'], 'files': files}


def publication_needed(expected, public):
    """A different date OR any changed asset requires a new publication."""
    return expected != public


def read_public_manifest(expected, opener=urlopen):
    # Bypass a cached response after publication without placing credentials in a URL.
    digest = hashlib.sha256(json.dumps(expected, sort_keys=True).encode()).hexdigest()[:20]
    request = Request(PUBLIC_MANIFEST + '?expected=' + digest,
                      headers={'Accept': 'application/json', 'Cache-Control': 'no-cache',
                               'User-Agent': 'A4C-C3-Pages-Health'})
    try:
        with opener(request, timeout=20) as response:
            raw = response.read(1024 * 1024 + 1)
    except HTTPError as error:
        if error.code == 404:
            return None
        raise
    if len(raw) > 1024 * 1024:
        raise ValueError('Public C3 manifest exceeds its size limit')
    try:
        return json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    expected = build_manifest()
    (ROOT / 'maquette/dist' / MANIFEST_NAME).write_text(
        json.dumps(expected, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    if args.check:
        needed = publication_needed(expected, read_public_manifest(expected))
        result = {'needs_deploy': needed, 'last_date': expected['last_date']}
        print(json.dumps(result))
        if os.environ.get('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf8') as output:
                output.write('needs_deploy=' + str(needed).lower() + '\n')


if __name__ == '__main__':
    main()
