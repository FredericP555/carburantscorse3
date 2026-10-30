"""Offline regressions for frozen history, retired comparisons and official brands."""
import copy,unittest
from datetime import date,datetime,timezone
from pathlib import Path
import pandas as pd
from assemble_current import total_point
from refresh_brands import refresh_registry,blocks_legacy_category
import test_current as current_checks


class RegressionTests(unittest.TestCase):
    def test_revised_frozen_day_does_not_block_a_new_valid_day(self):
        baseline={'end':'2026-10-26','dates':['2026-10-26'],'fuels':{'SP95':{'e10_gaps':{'all':[10.32],'reseau':[10.32]}}}}
        data=copy.deepcopy(baseline);data['end']='2026-10-27';data['dates'].append('2026-10-27')
        for rows in data['fuels']['SP95']['e10_gaps'].values():rows.append(10.0)
        c=current_checks.CurrentTests();c.data=data;c.seed=baseline;c.baseline=baseline
        c.s=pd.DataFrame([
            {'date':d,'department':dep,'fuel':fuel,'eligible_publication':True,'category':'network','price_ht':price}
            for d,cp in [('2026-10-26',9.0),('2026-10-27',2.0)]
            for dep,fuel,price in [('20','SP95',cp),('13','E10',1.9)]])
        c.test_new_e10_series_matches_same_station_weights_and_vat()
        c.test_history_is_preserved_for_every_displayed_series()
        c.data['fuels']['SP95']['e10_gaps']['all'][-1]=99
        with self.assertRaises(AssertionError):c.test_new_e10_series_matches_same_station_weights_and_vat()
        c.data['fuels']['SP95']['e10_gaps']['all'][0]=99
        with self.assertRaises(AssertionError):c.test_history_is_preserved_for_every_displayed_series()

    def test_retired_sp95_can_be_empty_but_displayed_gazole_remains_guarded(self):
        frame=pd.DataFrame([{'date':'2026-10-30','fuel':'SP95','brand_segment':'traditionnel',
                            'brand':'Total','department':'20','category':'network',
                            'station_id':'20001','price_ht':2.0}])
        row=total_point(frame,'2026-10-30','SP95')
        self.assertIsNone(row['diagnostic']);self.assertEqual(row['status'],'unavailable')
        with self.assertRaises(ValueError):total_point(frame,'2026-10-30','Gazole')

    def test_brand_change_is_dated_and_old_brand_is_preserved(self):
        registry={'stations':{'13001':{'enseigne':'Total','segment':'traditionnel','detail':'major_tradi',
                  'brand_valid_from':'2026-09-08','first_seen':'2026-09-08','verified_at':'2026-01-01'}}}
        obs=[{'station_id':'13001','department':'13','date':'2026-10-30','pop':'R','is_motorway':False}]
        result,audit=refresh_registry(registry,obs,'13',{},Path(__file__).with_suffix('.missing.csv'),
                       fetcher=lambda sid:('TotalEnergies Access',None),today=date(2026,10,31),
                       now=datetime(2026,10,31,tzinfo=timezone.utc))
        row=result['stations']['13001']
        self.assertEqual(row['brand_valid_from'],'2026-10-31')
        self.assertEqual(row['segment'],'gms_lowcost')
        self.assertEqual(row['brand_history'][0]['enseigne'],'Total')
        self.assertEqual(row['brand_history'][0]['valid_to'],'2026-10-30')
        self.assertFalse(blocks_legacy_category(row))
        self.assertEqual(registry['stations']['13001']['enseigne'],'Total')

    def test_legacy_historical_unknown_keeps_its_original_category(self):
        self.assertFalse(blocks_legacy_category({'enseigne':'Dyneff','segment':'inconnu'}))

    def test_transient_brand_failure_preserves_known_identity_and_reports_it(self):
        registry={'stations':{'20001':{'enseigne':'Eni','segment':'traditionnel','detail':'major_tradi',
                  'brand_valid_from':'2026-09-08','first_seen':'2026-09-08','verified_at':'2026-01-01'}}}
        obs=[{'station_id':'20001','department':'20','date':'2026-10-30','pop':'R','is_motorway':False}]
        result,audit=refresh_registry(registry,obs,'20',{},Path(__file__).with_suffix('.missing.csv'),
                       fetcher=lambda sid:(None,'HTTP503'),today=date(2026,10,31))
        self.assertEqual(result,registry);self.assertIn('20001',audit['errors'])

    def test_new_unrecognised_brand_is_not_guessed(self):
        obs=[{'station_id':'13999','department':'13','date':'2026-10-30','pop':'R','is_motorway':False}]
        result,audit=refresh_registry({'stations':{}},obs,'13',{},Path(__file__).with_suffix('.missing.csv'),
                       fetcher=lambda sid:('Unknown business name',None),today=date(2026,10,31))
        self.assertEqual(result['stations']['13999']['segment'],'inconnu');self.assertIn('13999',audit['unresolved_ids'])

    def test_official_unknown_change_retires_the_previous_total_identity(self):
        registry={'stations':{'13001':{'enseigne':'Total','segment':'traditionnel','detail':'major_tradi',
                  'brand_valid_from':'2026-09-08','first_seen':'2026-09-08','verified_at':'2026-01-01'}}}
        obs=[{'station_id':'13001','department':'13','date':'2026-10-30','pop':'R','is_motorway':False}]
        result,audit=refresh_registry(registry,obs,'13',{},Path(__file__).with_suffix('.missing.csv'),
                       fetcher=lambda sid:('Unknown business name',None),today=date(2026,10,31))
        row=result['stations']['13001']
        self.assertEqual(row['segment'],'inconnu');self.assertEqual(row['enseigne'],'Unknown business name')
        self.assertTrue(blocks_legacy_category(row))
        self.assertEqual(row['brand_valid_from'],'2026-10-31')
        self.assertEqual(row['brand_history'][0]['enseigne'],'Total')
        self.assertEqual(row['brand_history'][0]['valid_to'],'2026-10-30')


if __name__=='__main__':unittest.main(defaultTest='RegressionTests')
