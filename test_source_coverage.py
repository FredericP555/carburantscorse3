"""Snapshot coverage is distinct from the date of the latest price change.

All fixtures are isolated ZIP/XML snapshots and annual-observation CSVs. These
tests never download inputs or modify published data.
"""
from pathlib import Path
import copy
import csv
import gzip
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

from source_coverage import validate_source_coverage


GROUPS = ('13/Gazole', '13/SP95', '13/E10', '20/Gazole', '20/SP95')
FIELDS = ('source_year', 'station_id', 'department', 'cp', 'city', 'address',
          'pop', 'is_motorway', 'latitude', 'longitude', 'fuel_id', 'fuel',
          'timestamp', 'date', 'price', 'price_in_reference_band')


def declarations(timestamp='2026-10-31T12:00:00'):
    rows = []
    for index, group in enumerate(GROUPS, 1):
        department, fuel = group.split('/')
        rows.append({
            'source_year': timestamp[:4],
            'station_id': department + str(index).zfill(6),
            'department': department,
            'cp': department + '000',
            'city': 'Fixture', 'address': 'Fixture', 'pop': 'R',
            'is_motorway': 'False', 'latitude': '0', 'longitude': '0',
            'fuel_id': {'Gazole': '1', 'SP95': '2', 'E10': '5'}[fuel],
            'fuel': fuel, 'timestamp': timestamp, 'date': timestamp[:10],
            'price': '2.250', 'price_in_reference_band': 'True',
        })
    return rows


class SourceCoverageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(
            prefix='c3-source-coverage-', dir=Path(__file__).resolve().parent)
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.sources = self.root / 'sources'
        self.sources.mkdir()
        self.observations = self.root / 'observations.csv.gz'

    def write_observations(self, rows):
        with gzip.open(self.observations, 'wt', encoding='utf8', newline='') as output:
            writer = csv.DictWriter(output, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    def write_snapshot(self, day, rows, *, member_day=None):
        root = ET.Element('pdv_liste')
        stations = {}
        for row in rows:
            sid = row['station_id']
            if sid not in stations:
                stations[sid] = ET.SubElement(root, 'pdv', {
                    'id': sid, 'cp': row['cp'], 'pop': row.get('pop', 'R')})
            ET.SubElement(stations[sid], 'prix', {
                'nom': row['fuel'], 'id': row['fuel_id'],
                'maj': row['timestamp'], 'valeur': row['price']})
        member_day = member_day or day
        name = 'PrixCarburants_quotidien_' + member_day.replace('-', '') + '.xml'
        target = self.sources / ('daily_' + day.replace('-', '') + '.zip')
        with zipfile.ZipFile(target, 'w') as output:
            output.writestr(name, ET.tostring(root, encoding='utf8'))
        return target

    def validate(self, *days):
        return validate_source_coverage(self.sources, self.observations, list(days))

    def test_sunday_without_new_declarations_is_covered(self):
        rows = declarations('2026-10-31T12:00:00')
        self.write_observations(rows)
        self.write_snapshot('2026-11-01', rows)
        report = self.validate('2026-11-01')
        groups = report['days']['2026-11-01']['groups']
        self.assertEqual(set(groups), set(GROUPS))
        for group in GROUPS:
            self.assertEqual(groups[group]['prices'], 1)
            self.assertEqual(groups[group]['matched_declarations'], 1)
            self.assertEqual(str(groups[group]['last_declaration'])[:10], '2026-10-31')

    def test_only_sp95_changes_in_corsica_on_sunday(self):
        old = declarations()
        rows = copy.deepcopy(old)
        rows[-1].update(timestamp='2026-11-01T09:00:00', date='2026-11-01', price='2.280')
        self.write_observations(old + [rows[-1]])
        self.write_snapshot('2026-11-01', rows)
        report = self.validate('2026-11-01')['days']['2026-11-01']['groups']
        self.assertEqual(str(report['20/Gazole']['last_declaration'])[:10], '2026-10-31')
        self.assertEqual(str(report['20/SP95']['last_declaration'])[:10], '2026-11-01')

    def test_missing_annual_declaration_is_rejected(self):
        rows = declarations()
        self.write_observations(rows[:-1])
        self.write_snapshot('2026-11-01', rows)
        with self.assertRaises(ValueError):
            self.validate('2026-11-01')

    def test_matching_timestamp_with_different_annual_price_is_rejected(self):
        rows = declarations()
        annual = copy.deepcopy(rows)
        annual[-1]['price'] = '2.260'
        self.write_observations(annual)
        self.write_snapshot('2026-11-01', rows)
        with self.assertRaises(ValueError):
            self.validate('2026-11-01')

    def test_equal_numeric_prices_and_iso_timestamp_formats_match(self):
        annual = declarations()
        daily = copy.deepcopy(annual)
        for row in daily:
            row['price'] = '2.25'
            row['timestamp'] = row['timestamp'].replace('T', ' ')
        self.write_observations(annual)
        self.write_snapshot('2026-11-01', daily)
        self.assertIn('2026-11-01', self.validate('2026-11-01')['days'])

    def test_wrong_snapshot_member_date_is_rejected(self):
        rows = declarations()
        self.write_observations(rows)
        self.write_snapshot('2026-11-01', rows, member_day='2026-10-31')
        with self.assertRaises((ValueError, RuntimeError)):
            self.validate('2026-11-01')

    def test_missing_snapshot_is_rejected(self):
        self.write_observations(declarations())
        with self.assertRaises((ValueError, RuntimeError, FileNotFoundError)):
            self.validate('2026-11-01')

    def test_empty_snapshot_is_rejected(self):
        self.write_observations(declarations())
        self.write_snapshot('2026-11-01', [])
        with self.assertRaises(ValueError):
            self.validate('2026-11-01')

    def test_each_required_group_must_be_present(self):
        for group in GROUPS:
            with self.subTest(group=group):
                rows = declarations()
                self.write_observations(rows)
                self.write_snapshot('2026-11-01', [
                    row for row in rows if row['department'] + '/' + row['fuel'] != group])
                with self.assertRaises(ValueError):
                    self.validate('2026-11-01')

    def test_future_declaration_is_rejected(self):
        rows = declarations()
        rows[-1].update(timestamp='2026-11-02T00:00:00', date='2026-11-02')
        self.write_observations(rows)
        self.write_snapshot('2026-11-01', rows)
        with self.assertRaises(ValueError):
            self.validate('2026-11-01')

    def test_malformed_timestamp_is_rejected(self):
        rows = declarations()
        self.write_observations(rows)
        rows[-1]['timestamp'] = 'not-a-timestamp'
        self.write_snapshot('2026-11-01', rows)
        with self.assertRaises(ValueError):
            self.validate('2026-11-01')

    def test_malformed_or_nonfinite_price_is_rejected(self):
        for price in ('not-a-price', '', 'NaN', 'Infinity'):
            with self.subTest(price=price):
                rows = declarations()
                self.write_observations(rows)
                rows[-1]['price'] = price
                self.write_snapshot('2026-11-01', rows)
                with self.assertRaises(ValueError):
                    self.validate('2026-11-01')

    def test_out_of_band_price_remains_a_real_observation(self):
        rows = declarations()
        rows[-1]['price'] = '4.000'
        rows[-1]['price_in_reference_band'] = 'False'
        self.write_observations(rows)
        self.write_snapshot('2026-11-01', rows)
        report = self.validate('2026-11-01')
        self.assertEqual(report['days']['2026-11-01']['groups']['20/SP95']['matched_declarations'], 1)

    def test_every_catchup_day_requires_its_own_snapshot(self):
        first = declarations('2026-10-31T12:00:00')
        second = declarations('2026-11-02T12:00:00')
        self.write_observations(first + second)
        self.write_snapshot('2026-11-01', first)
        self.write_snapshot('2026-11-02', second)
        report = self.validate('2026-11-01', '2026-11-02')
        self.assertEqual(set(report['days']), {'2026-11-01', '2026-11-02'})
        (self.sources / 'daily_20261101.zip').unlink()
        with self.assertRaises((ValueError, RuntimeError, FileNotFoundError)):
            self.validate('2026-11-01', '2026-11-02')

    def test_january_snapshot_can_match_previous_year_declarations(self):
        rows = declarations('2026-12-31T12:00:00')
        self.write_observations(rows)
        self.write_snapshot('2027-01-01', rows)
        report = self.validate('2027-01-01')['days']['2027-01-01']['groups']
        self.assertEqual(str(report['20/Gazole']['last_declaration'])[:10], '2026-12-31')

    def test_motorway_rows_do_not_supply_or_break_public_coverage(self):
        rows = declarations()
        motorway = copy.deepcopy(rows[-1])
        motorway.update(station_id='20999999', pop='A', is_motorway='True',
                        timestamp='not-a-timestamp', price='not-a-price')
        self.write_observations(rows)
        self.write_snapshot('2026-11-01', rows + [motorway])
        self.assertIn('2026-11-01', self.validate('2026-11-01')['days'])
        rows[-1].update(pop='A', is_motorway='True')
        self.write_snapshot('2026-11-01', rows)
        with self.assertRaises(ValueError):
            self.validate('2026-11-01')

    def test_older_than_available_annual_history_is_not_a_missing_observation(self):
        rows = declarations()
        old = copy.deepcopy(rows[-1])
        old.update(station_id='20999999', timestamp='2024-12-01T10:00:00',
                   date='2024-12-01', source_year='2024')
        self.write_observations(rows)
        self.write_snapshot('2026-11-01', rows + [old])
        self.assertIn('2026-11-01', self.validate('2026-11-01')['days'])

    def test_old_only_group_cannot_pass_without_a_matchable_observation(self):
        rows = declarations()
        self.write_observations(rows[:-1])
        rows[-1].update(timestamp='2024-12-01T10:00:00', date='2024-12-01', source_year='2024')
        self.write_snapshot('2026-11-01', rows)
        with self.assertRaises(ValueError):
            self.validate('2026-11-01')


if __name__ == '__main__':
    unittest.main()
