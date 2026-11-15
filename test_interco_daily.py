"""EPCI aggregation must partition the regional sample, never reselect stations."""
import copy
import tempfile
import unittest
from pathlib import Path
import pandas as pd
from interco_daily import append_intercos, load_geography
from daily_refresh import revalidation_seed


class IntercoTests(unittest.TestCase):
    def fixture(self, days=('2026-12-31', '2027-01-01')):
        geo = pd.DataFrame([dict(station_id='a',epci_siren='1',epci_nom='Territoire A'),
                            dict(station_id='b',epci_siren='1',epci_nom='Territoire A'),
                            dict(station_id='c',epci_siren='2',epci_nom='Territoire B'),
                            dict(station_id='d',epci_siren='3',epci_nom='Sans donnée')])
        rows=[]
        for day in days:
            for fuel,extra in [('Gazole',0),('SP95',.1)]:
                for station,price,eligible in [('a',2,True),('b',2.1,True),('c',2.2,True),('d',1.5,False)]:
                    rows.append(dict(date=day,station_id=station,region='corse',fuel=fuel,
                                     price=price+extra,eligible=eligible))
        data=dict(dates=list(days),end=days[-1],fuels={f:dict(regions={'Corse':[v]*len(days)})
                  for f,v in [('Gazole',2.1),('SP95',2.2)]})
        return data,pd.DataFrame(rows),geo

    def test_equal_station_weights_separate_fuels_empty_sample_and_year_boundary(self):
        data,rows,geo=self.fixture()
        append_intercos(data,rows,data['dates'],geo)
        for fuel,offset in [('Gazole',0),('SP95',.1)]:
            s=data['fuels'][fuel]['intercos']
            self.assertEqual(s['1']['prices'],[round(2.05+offset,3)]*2)
            self.assertEqual(s['1']['counts'],[2,2])
            self.assertEqual(s['2']['prices'],[round(2.2+offset,3)]*2)
            self.assertEqual(s['3']['prices'],[None,None])
            self.assertEqual(s['3']['counts'],[0,0])

    def test_unknown_station_blocks_even_when_ineligible(self):
        data,rows,geo=self.fixture()
        rows.loc[rows.station_id.eq('d'),'station_id']='unmapped'
        with self.assertRaisesRegex(ValueError,'Unmapped'):append_intercos(data,rows,data['dates'],geo)

    def test_duplicates_and_disagreement_with_regional_mean_block(self):
        data,rows,geo=self.fixture()
        with self.assertRaisesRegex(ValueError,'Duplicate'):append_intercos(data,pd.concat([rows,rows.iloc[:1]]),data['dates'],geo)
        data['fuels']['Gazole']['regions']['Corse'][0]=2.8
        with self.assertRaisesRegex(ValueError,'published Corsica mean'):append_intercos(data,rows,data['dates'],geo)

    def test_append_preserves_history_and_revalidation_trims_every_field(self):
        data,rows,geo=self.fixture()
        first=copy.deepcopy(data);first['dates']=first['dates'][:1];first['end']=first['dates'][0]
        for node in first['fuels'].values():node['regions']['Corse']=node['regions']['Corse'][:1]
        append_intercos(first,rows,first['dates'],geo)
        before=copy.deepcopy(first)
        for f in first['fuels']:first['fuels'][f]['regions']['Corse'].append(data['fuels'][f]['regions']['Corse'][1])
        append_intercos(first,rows,[data['dates'][1]],geo)
        first['dates']=data['dates'];first['end']=data['end']
        for fuel in first['fuels']:
            for key,node in before['fuels'][fuel]['intercos'].items():
                for field in ('prices','counts','samples'):self.assertEqual(first['fuels'][fuel]['intercos'][key][field][:-1],node[field])
        trimmed=revalidation_seed(first,'2027-01-01')
        self.assertEqual(trimmed,before)

    def test_missing_prefix_cannot_silently_restart_series(self):
        data,rows,geo=self.fixture()
        with self.assertRaisesRegex(ValueError,'Incomplete'):append_intercos(data,rows,[data['dates'][1]],geo)

    def test_current_geography_and_its_fail_closed_contract(self):
        geo=load_geography()
        self.assertEqual(geo.epci_siren.nunique(),19)
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
            path=Path(directory)/'geo.csv'
            pd.concat([geo,geo.iloc[:1]]).to_csv(path,index=False)
            with self.assertRaisesRegex(ValueError,'Duplicate'):load_geography(path)
            broken=geo.copy();broken.loc[0,'epci_siren']='';broken.to_csv(path,index=False)
            with self.assertRaisesRegex(ValueError,'Incomplete'):load_geography(path)


if __name__=='__main__':unittest.main()
