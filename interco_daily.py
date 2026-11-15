"""Daily EPCI means reuse C3's regional station eligibility without changing it."""
from pathlib import Path
import hashlib
import math
import pandas as pd

ROOT = Path(__file__).resolve().parent
GEOGRAPHY = ROOT / 'config/corse_station_geography_2026.csv'


def load_geography(path=GEOGRAPHY):
    geo = pd.read_csv(path, dtype=str).fillna('')
    required = ('station_id', 'commune', 'epci_siren', 'epci_nom')
    if any(k not in geo or geo[k].str.strip().eq('').any() for k in required):
        raise ValueError('Incomplete C3 intercommunal geography')
    if geo.station_id.duplicated().any():
        raise ValueError('Duplicate station in C3 geography')
    if (geo.groupby('epci_siren').epci_nom.nunique() != 1).any():
        raise ValueError('Conflicting EPCI names')
    if geo.epci_siren.nunique() != 19:
        raise ValueError('C3 geography must contain the 19 Corsican EPCI')
    return geo


def append_intercos(data, regional, days, geography=None):
    geo = load_geography() if geography is None else geography
    rows = regional[regional.region.eq('corse') & regional.fuel.isin(('Gazole', 'SP95'))
                    & regional.date.isin(days)].copy()
    if rows.duplicated(['date', 'fuel', 'station_id']).any():
        raise ValueError('Duplicate C3 regional station-day')
    missing = sorted(set(rows.station_id) - set(geo.station_id))
    if missing:
        raise ValueError('Unmapped Corsican station IDs: ' + ', '.join(missing))
    rows = rows.merge(geo[['station_id', 'epci_siren']], on='station_id', validate='many_to_one')
    catalog = geo[['epci_siren', 'epci_nom']].drop_duplicates().sort_values('epci_siren')
    for fuel, node in data['fuels'].items():
        all_series = node.setdefault('intercos', {})
        for entry in catalog.itertuples(index=False):
            series = all_series.setdefault(entry.epci_siren,
                dict(name=entry.epci_nom, prices=[], counts=[], samples=[]))
            if series['name'] != entry.epci_nom:
                raise ValueError('EPCI name changed without migration')
        if set(all_series) != set(catalog.epci_siren):
            raise ValueError('C3 EPCI catalog mismatch')
        for offset, day in enumerate(days):
            index = data['dates'].index(day) if day in data['dates'] else len(data['dates']) + offset
            good = rows[rows.date.eq(day) & rows.fuel.eq(fuel) & rows.eligible]
            if good.empty or not good.price.between(1.10, 3.00).all():
                raise ValueError('Invalid or empty Corsican regional sample')
            # Cross-check the unrounded national-region calculation at displayed precision.
            expected = node['regions']['Corse'][index]
            if round(float(good.price.mean()) + 1e-12, 3) != expected:
                raise ValueError('EPCI input does not match published Corsica mean: ' + day)
            for sid, series in all_series.items():
                if any(len(series[k]) != index for k in ('prices', 'counts', 'samples')):
                    raise ValueError('Incomplete C3 EPCI history')
                selected = good[good.epci_siren.eq(sid)]
                value = round(math.fsum(selected.price) / len(selected) + 1e-12, 3) if len(selected) else None
                series['prices'].append(value)
                series['counts'].append(len(selected))
                signature = '\n'.join(sorted(selected.station_id))
                series['samples'].append(hashlib.sha256(signature.encode()).hexdigest()[:16])
