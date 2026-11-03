"""Checks for the independent C3 run and preserved history."""
from pathlib import Path
import copy,json,re,unittest
import pandas as pd
ROOT=Path(__file__).resolve().parent

class CurrentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads((ROOT/'data/current.json').read_text(encoding='utf8'))
        cls.seed=json.loads((ROOT/'data/history_20261025.json').read_text(encoding='utf8'))
        cls.out=ROOT/'outputs/runs'/cls.data['provenance']['last_run']
        baseline=cls.out/'baseline.json'
        cls.baseline=json.loads(baseline.read_text(encoding='utf8')) if baseline.exists() else cls.seed
        cls.s=pd.read_csv(cls.out/'territorial_stations.csv.gz',dtype={'department':str,'station_id':str})

    def new_dates(self):
        return [day for day in self.data['dates'] if day>self.baseline['end']]

    def test_history_is_preserved_for_every_displayed_series(self):
        for baseline in (self.seed,self.baseline):
            n=len(baseline['dates'])
            self.assertEqual(self.data['dates'][:n],baseline['dates'])
            for fuel,old in baseline['fuels'].items():
                new=self.data['fuels'][fuel]
                for group in ('regions','gaps','e10_gaps'):
                    for name,values in old.get(group,{}).items():self.assertEqual(new[group][name][:n],values)
                for group in ('total','total_all','eni'):
                    if group in old:self.assertEqual(new[group][:n],old[group])

    def test_dates_and_lengths(self):
        dates=pd.date_range(self.data['start'],self.data['end']).strftime('%Y-%m-%d').tolist()
        self.assertEqual(dates,self.data['dates'])
        for values in self.data['fuels'].values():
            for group in ('regions','gaps','e10_gaps'):
                for rows in values.get(group,{}).values():self.assertEqual(len(rows),len(dates))
            for group in ('total','total_all','eni'):
                if group in values:self.assertEqual(len(values[group]),len(dates))

    def test_no_motorway_or_invalid_prices_in_retained_state(self):
        self.assertFalse(self.s['pop'].eq('A').any())
        self.assertFalse(self.s.duplicated(['date','station_id','fuel']).any())
        retained=self.s[self.s.eligible_publication]
        self.assertTrue(retained.price.between(1.10,3.00).all())
        expected=(retained.price / retained.department.map({'20':1.13,'13':1.20})).round(4)
        self.assertTrue((expected-retained.price_ht).abs().lt(1e-8).all())

    def test_no_unavailable_r2_or_unknown_new_bdr(self):
        audit=json.loads((self.out/'territorial_audit.json').read_text(encoding='utf8'))
        self.assertFalse(audit['engine']['r2_errors']);self.assertEqual(audit['engine']['r2_unavailable'],0)
        self.assertFalse(audit['unknown_new_bdr'])

    def test_new_e10_series_matches_same_station_weights_and_vat(self):
        good=self.s[self.s.eligible_publication]
        for day in self.new_dates():
            i=self.data['dates'].index(day);c=good[(good.date==day)&good.department.eq('20')&good.fuel.eq('SP95')]
            for scope in ('all','reseau'):
                b=good[(good.date==day)&good.department.eq('13')&good.fuel.eq('E10')]
                if scope=='reseau':b=b[b.category.eq('network')]
                self.assertEqual(self.data['fuels']['SP95']['e10_gaps'][scope][i],round(100*(c.price_ht.mean()-b.price_ht.mean()),2))

    def test_new_brand_means_and_counts(self):
        from assemble_current import total
        good=self.s[self.s.eligible_publication & self.s.fuel.eq('Gazole') & self.s.brand_segment.eq('traditionnel')]
        for day in self.new_dates():
            i=self.data['dates'].index(day)
            for key in ('total','eni'):
                selected=good[good.date.eq(day)&(good.brand.map(total) if key=='total' else good.brand.fillna('').str.casefold().eq('eni'))]
                c=selected[selected.department.eq('20')];b=selected[selected.department.eq('13')]
                row=self.data['fuels']['Gazole'][key][i]
                self.assertEqual(row['n_corse'],len(c));self.assertEqual(row['n_bdr'],len(b))
                self.assertEqual(row['diagnostic' if key=='total' else 'gap'],round(100*(c.price_ht.mean()-b.price_ht.mean()),2))
                if key=='total':self.assertFalse(selected.brand.str.contains('access|elan|élan',case=False).any())

    def test_runtime_scripts_do_not_import_reference_checkouts(self):
        for name in ('run_regions.py','run_territories.py','assemble_current.py','build_mockup.py'):
            text=(ROOT/name).read_text(encoding='utf8');self.assertNotIn('reference-c1',text);self.assertNotIn('reference-c2',text)
        self.assertTrue((ROOT/'assets/chart.min.js').exists())

    def test_access_inclusive_series_matches_station_means_and_same_corsica(self):
        good=self.s[self.s.eligible_publication & self.s.fuel.eq('Gazole')]
        names=good.brand.fillna('').str.casefold().str.replace('[^a-z0-9]','',regex=True)
        regular={'total','totalenergies','totalcontact','totalenergiescontact'}
        for day in self.new_dates():
            i=self.data['dates'].index(day)
            c=good[good.date.eq(day)&good.department.eq('20')&good.brand_segment.eq('traditionnel')&names.isin(regular)]
            b=good[good.date.eq(day)&good.department.eq('13')&names.isin(regular|{'totalaccess','totalenergiesaccess'})]
            row=self.data['fuels']['Gazole']['total_all'][i]
            self.assertEqual(row['diagnostic'],round(100*(c.price_ht.mean()-b.price_ht.mean()),2))
            self.assertEqual(row['n_corse'],len(c))
            self.assertEqual(row['n_corse'],self.data['fuels']['Gazole']['total'][i]['n_corse'])
            self.assertEqual(row['n_bdr'],len(b))
            self.assertGreaterEqual(row['n_bdr'],self.data['fuels']['Gazole']['total'][i]['n_bdr'])
            self.assertFalse(b['pop'].eq('A').any())

if __name__=='__main__':unittest.main()
