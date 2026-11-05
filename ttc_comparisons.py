"""TTC gaps from exactly the eligible station populations used for HTVA gaps."""
from assemble_current import total, total_with_access


def point(good, day, fuel):
    rows = good[good.date.eq(day)]
    c = rows[rows.department.eq('20') & rows.fuel.eq(fuel)]
    def gap(corse, bdr):
        if corse.empty or bdr.empty:
            raise ValueError(f'TTC comparison unavailable: {day} {fuel}')
        return round(100 * (corse.price.mean() - bdr.price.mean()), 2)
    result = {}
    for bf, prefix in [(fuel, 'gaps'), *([('E10', 'e10')] if fuel == 'SP95' else [])]:
        b = rows[rows.department.eq('13') & rows.fuel.eq(bf)]
        for scope in ('all', 'reseau'):
            result[f'{prefix}_{scope}'] = gap(c, b if scope == 'all' else b[b.category.eq('network')])
    if fuel == 'Gazole':
        cf = c[c.brand_segment.eq('traditionnel')]
        b = rows[rows.department.eq('13') & rows.fuel.eq(fuel)]
        cb = cf[cf.brand.map(total).astype(bool)]
        result['total'] = gap(cb, b[b.brand_segment.eq('traditionnel') & b.brand.map(total).astype(bool)])
        result['total_all'] = gap(cb, b[b.brand.map(total_with_access).astype(bool)])
        result['eni'] = gap(cf[cf.brand.fillna('').str.casefold().eq('eni')],
                            b[b.brand_segment.eq('traditionnel') & b.brand.fillna('').str.casefold().eq('eni')])
    return result


def append_ttc(data, good, days):
    for fuel, node in data['fuels'].items():
        for day in days:
            values = point(good, day, fuel)
            expected = data['dates'].index(day) if day in data['dates'] else len(data['dates']) + days.index(day)
            for key, value in values.items():
                series = node.setdefault('ttc', {}).setdefault(key, [])
                if len(series) != expected:
                    raise ValueError(f'Incomplete TTC history: {fuel} {key}')
                series.append(value)
