"""Total Access expands BDR only and keeps station weights and frozen history."""
from datetime import date
import copy, unittest
import pandas as pd
from assemble_current import total_point
from daily_refresh import revalidation_seed


class TotalAccessTests(unittest.TestCase):
    def rows(self):
        return pd.DataFrame([
            dict(date='2026-11-02', fuel='Gazole', station_id=sid, department=dep,
                 brand=brand, brand_segment=segment, category=category, price_ht=price)
            for sid, dep, brand, segment, category, price in [
                ('c1', '20', 'TotalEnergies', 'traditionnel', 'network', 2.0),
                ('c-access', '20', 'TotalEnergies Access', 'gms_lowcost', 'gms', 1.0),
                ('b1', '13', 'TotalEnergies', 'traditionnel', 'network', 1.9),
                ('b2', '13', 'TotalEnergies Contact', 'traditionnel', 'network', 1.8),
                ('a1', '13', 'TotalEnergies Access', 'gms_lowcost', 'gms', 1.5),
                ('a2', '13', 'Total Access', 'gms_lowcost', 'gms', 1.6),
                ('elan', '13', 'Élan', 'traditionnel', 'network', 1.0),
                ('shell', '13', 'Shell', 'traditionnel', 'network', 1.0)]])

    def test_only_bdr_expands_and_each_station_has_equal_weight(self):
        frame = self.rows()
        without = total_point(frame, '2026-11-02', 'Gazole')
        with_access = total_point(frame, '2026-11-02', 'Gazole', include_access=True)
        self.assertEqual(without['diagnostic'], 15.0)
        self.assertEqual(with_access['diagnostic'], 30.0)
        self.assertEqual(without['n_corse'], 1)
        self.assertEqual(with_access['n_corse'], 1)
        self.assertEqual(without['n_bdr'], 2)
        self.assertEqual(with_access['n_bdr'], 4)
        self.assertEqual(len(frame), 8)

    def test_same_result_without_access_rows_and_empty_target_guard(self):
        frame = self.rows()
        frame = frame[~frame.brand.str.contains('Access')]
        self.assertEqual(total_point(frame, '2026-11-02', 'Gazole'),
                         total_point(frame, '2026-11-02', 'Gazole', include_access=True))
        with self.assertRaises(ValueError):
            total_point(frame[frame.department.eq('20')], '2026-11-02', 'Gazole', include_access=True)

    def test_revalidation_trims_new_series_with_the_other_series(self):
        current = {'end': '2026-11-02', 'dates': ['2026-10-31', '2026-11-01', '2026-11-02'],
                   'fuels': {'Gazole': {'regions': {}, 'total': [1, 2, 3],
                                        'total_all': [4, 5, 6], 'eni': [7, 8, 9]}}}
        before = copy.deepcopy(current)
        seed = revalidation_seed(current, '2026-11-02')
        self.assertEqual(seed['fuels']['Gazole']['total_all'], [4, 5])
        self.assertEqual(current, before)


class TtcTests(unittest.TestCase):
    def test_same_prices_ttc_can_have_different_htva(self):
        from ttc_comparisons import point
        frame = TotalAccessTests().rows()
        frame['price'] = 2.0
        frame['price_ht'] = frame.price / frame.department.map({'20': 1.13, '13': 1.20})
        # Make the ENI group present too, without changing the Total populations.
        eni = frame[frame.station_id.isin(['c1', 'b1'])].copy()
        eni['brand'] = 'Eni'
        frame = pd.concat([frame, eni], ignore_index=True)
        result = point(frame, '2026-11-02', 'Gazole')
        self.assertTrue(all(value == 0 for value in result.values()))
        self.assertGreater(total_point(frame, '2026-11-02', 'Gazole')['diagnostic'], 10)

    def test_ttc_seed_trimming_and_alignment_guard(self):
        from ttc_comparisons import append_ttc
        current = {'dates': ['2026-11-01', '2026-11-02'], 'end': '2026-11-02',
                   'fuels': {'Gazole': {'regions': {}, 'ttc': {'total': [1, 2]}}}}
        self.assertEqual(revalidation_seed(current, '2026-11-02')['fuels']['Gazole']['ttc']['total'], [1])


if __name__ == '__main__':
    unittest.main()
