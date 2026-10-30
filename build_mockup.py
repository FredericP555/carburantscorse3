"""Build the C3 website and standalone page from C3-owned data and assets."""
from pathlib import Path
from datetime import date
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parent
DEST = ROOT / 'maquette/dist'
MONTHS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin',
          'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']


def date_label(value):
    day = date.fromisoformat(value)
    return f'{day.day} {MONTHS[day.month - 1]} {day.year}'


def render_page(template, data):
    start, end = (date.fromisoformat(data[key]) for key in ('start', 'end'))
    values = {
        'START_DATE': data['start'],
        'END_DATE': data['end'],
        'START_LABEL': date_label(data['start']),
        'END_LABEL': date_label(data['end']),
        'PERIOD_LABEL': f'{date_label(data["start"])} – {date_label(data["end"])}',
        'START_SHORT': f'{start.day} {MONTHS[start.month - 1][:3].upper()}.',
        'END_SHORT': f'{end.day} {MONTHS[end.month - 1][:3].upper()}.',
        'DAY_COUNT': str(len(data['dates'])),
        'LAST_INDEX': str(len(data['dates']) - 1),
    }
    for key, value in values.items():
        template = template.replace('{{' + key + '}}', value)
    if re.search(r'\{\{[A-Z_]+\}\}', template):
        raise ValueError('Unresolved website template value')
    return template


def versioned_assets(html, directory):
    """Changing a file changes its URL, including data after each daily update."""
    for name in ('style.css', 'chart.min.js', 'data.js', 'app.js'):
        digest = hashlib.sha256((directory / name).read_bytes()).hexdigest()[:12]
        html = html.replace(f'"{name}"', f'"{name}?v={digest}"')
    return html


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    source = ROOT / 'data/current.json'
    if not source.exists():
        source = ROOT / 'data/history_20261025.json'
    data = json.loads(source.read_text(encoding='utf8'))
    (DEST / 'data.js').write_text(
        'window.C3_DATA = ' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + ';\n',
        encoding='utf8', newline='\n',
    )
    # Canonical line endings keep hashes identical on Windows and GitHub runners.
    (DEST / 'chart.min.js').write_text(
        (ROOT / 'assets/chart.min.js').read_text(encoding='utf8'),
        encoding='utf8', newline='\n',
    )
    for name in ('style.css', 'app.js'):
        (DEST / name).write_text(
            (ROOT / 'maquette' / name).read_text(encoding='utf8'),
            encoding='utf8', newline='\n',
        )
    template = (ROOT / 'maquette/index.html').read_text(encoding='utf8')
    html = render_page(template, data)
    (DEST / 'index.html').write_text(versioned_assets(html, DEST), encoding='utf8', newline='\n')
    standalone = html.replace(
        '<link rel="stylesheet" href="style.css">',
        '<style>' + (DEST / 'style.css').read_text(encoding='utf8') + '</style>',
    )
    for name in ('chart.min.js', 'data.js', 'app.js'):
        script = (DEST / name).read_text(encoding='utf8').replace('</script', '<\\/script')
        standalone = standalone.replace(f'<script src="{name}"></script>', '<script>' + script + '</script>')
    for target in (ROOT / 'maquette/C3.html', DEST / 'C3.html'):
        target.write_text(standalone, encoding='utf8', newline='\n')
    print(f'C3 static website: {len(data["dates"])} days, through {data["end"]}')


if __name__ == '__main__':
    main()
