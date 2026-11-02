"""Check dated official snapshots against the annual declarations used by C3.

A price need not change every day. Freshness belongs to the daily archive, while
the existing calculation engines retain responsibility for price age and events.
"""
from pathlib import Path
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import csv, gzip, io, zipfile
import xml.etree.ElementTree as ET

from collect_current import FIRST_SOURCE_YEAR, validate_archive

GROUPS = ('13/Gazole', '13/SP95', '13/E10', '20/Gazole', '20/SP95')


def declaration(station, department, fuel, timestamp, price):
    try:
        ts = datetime.fromisoformat(timestamp)
        value = Decimal(str(price))
        if not station or not value.is_finite():
            raise ValueError('identifiant ou prix invalide')
    except (ValueError, TypeError, InvalidOperation) as exc:
        raise ValueError(f'Déclaration officielle invalide : {station}/{fuel}') from exc
    return (station, department, fuel, ts.isoformat(), value)


def validate_source_coverage(src: Path, observations: Path, days: list[str]) -> dict:
    report = {'days': {}}
    expected = set()
    for day in days:
        target = date.fromisoformat(day)
        name = f'daily_{target:%Y%m%d}.zip'
        raw = (src / name).read_bytes()
        validate_archive(raw, name)
        groups = {key: {'prices': 0, 'last_declaration': '', 'matched_declarations': 0}
                  for key in GROUPS}
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            member = next(n for n in archive.namelist()
                          if n.rsplit('/', 1)[-1] == f'PrixCarburants_quotidien_{target:%Y%m%d}.xml')
            with archive.open(member) as stream:
                for _, station in ET.iterparse(stream, events=('end',)):
                    if station.tag.rsplit('}', 1)[-1] != 'pdv':
                        continue
                    cp = station.get('cp', '').strip()
                    department = '20' if cp.startswith('20') else cp[:2]
                    if len(cp) == 5 and cp.isdigit() and station.get('pop') != 'A':
                        for price in station:
                            fuel = price.get('nom', '')
                            key = department + '/' + fuel
                            if price.tag.rsplit('}', 1)[-1] != 'prix' or key not in groups:
                                continue
                            item = declaration(station.get('id', ''), department, fuel,
                                               price.get('maj'), price.get('valeur'))
                            declared = date.fromisoformat(item[3][:10])
                            if declared > target:
                                raise ValueError(f'Déclaration future dans {name} : {item[0]}/{fuel}')
                            group = groups[key]
                            group['prices'] += 1
                            group['last_declaration'] = max(group['last_declaration'], declared.isoformat())
                            # Earlier declarations predate the annual inputs and are
                            # already too old for the calculation's existing policy.
                            if declared.year >= FIRST_SOURCE_YEAR:
                                expected.add(item)
                                group['matched_declarations'] += 1
                    station.clear()
        for key, group in groups.items():
            if not group['prices'] or not group['matched_declarations']:
                raise ValueError(f'Source quotidienne incomplète : {day} {key}')
        report['days'][day] = {'groups': groups}

    remaining = expected.copy()
    if remaining:
        identities = {item[:4] for item in expected}
        with gzip.open(observations, 'rt', encoding='utf8', newline='') as stream:
            for row in csv.DictReader(stream):
                identity = (row['station_id'], row['department'], row['fuel'], row['timestamp'])
                if identity not in identities:
                    continue
                try:
                    item = declaration(*identity, row['price'])
                except ValueError:
                    # Invalid annual prices remain excluded by the engines and
                    # cannot stand in for a valid daily declaration here.
                    continue
                remaining.discard(item)
        if remaining:
            sample = sorted(remaining)[:5]
            raise ValueError(f'Archive annuelle incomplète ou incohérente : '
                             f'{len(remaining)} déclaration(s) du quotidien absente(s), exemples : {sample}')
    report['verified_declarations'] = len(expected)
    return report
