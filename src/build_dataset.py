"""Build the fixed-cohort panel from archived files only (no network)."""
from pathlib import Path
import json, re
import numpy as np
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT/'data/raw'
OUT = ROOT/'data/processed'
RANKS = {3:'assistant',2:'associate',1:'full'}

def csv(path, **kwargs):
    try: d=pd.read_csv(path,encoding='utf-8-sig',low_memory=False,**kwargs)
    except UnicodeDecodeError: d=pd.read_csv(path,encoding='latin1',low_memory=False,**kwargs)
    d.columns=d.columns.str.strip()
    return d

def choose(directory, prefix):
    files=[p for p in directory.glob('*_files/*.csv') if p.name.lower().startswith(prefix.lower())]
    if not files:return None
    # The archive often contains both provisional and final files. Prefer final.
    return sorted(files,key=lambda p:('_rv' in p.stem.lower(),p.name))[-1]

def relative(p):return str(p.relative_to(ROOT))
def numeric(x):
    v=pd.to_numeric(x,errors='coerce')
    return np.nan if pd.isna(v) or v<0 else float(v)

def colleges():
    source=RAW/'rankings/kickstart_2027.html'
    tables=pd.read_html(source)
    r=next(t for t in tables if 'Williams College' in t.iloc[:,0].values).rename(columns={'Institution':'college','Rank (2027)':'usnews_rank_2027','Rank (2026)':'usnews_rank_2026'})
    r=r[~r.college.str.startswith('United States')].sort_values(['usnews_rank_2027','college'])
    threshold=r.iloc[29].usnews_rank_2027
    r=r[r.usnews_rank_2027<=threshold].copy()
    hd_path=choose(RAW/'ipeds/2024','hd2024'); hd=csv(hd_path)
    c=r.merge(hd[hd.INSTNM.isin(r.college)],left_on='college',right_on='INSTNM',how='left',validate='one_to_one')
    assert c.UNITID.notna().all(), 'Unmatched college name'
    c=c[['college','UNITID','CITY','STABBR','COUNTYCD','COUNTYNM','CBSA','CBSATYPE','usnews_rank_2027','usnews_rank_2026']].rename(columns={'UNITID':'unitid','CITY':'city','STABBR':'state','COUNTYCD':'county_fips','COUNTYNM':'county_name','CBSA':'ipeds_cbsa_2024','CBSATYPE':'ipeds_cbsa_type_2024'})
    c['unitid']=c.unitid.astype(int);c['county_fips']=c.county_fips.astype(int).astype(str).str.zfill(5)
    c['state_fips']=c.county_fips.str[:2]
    c['ranking_source']=relative(source)
    c['ranking_quality']='secondary_transcription_publisher_access_blocked'
    c['location_source']=relative(hd_path)
    cross= pd.read_excel(RAW/'census/list1_2023.xlsx',skiprows=2,dtype=str)
    cross['county_fips']=cross['FIPS State Code'].fillna('')+cross['FIPS County Code'].fillna('')
    cross=cross[cross.county_fips.str.len()==5]
    assert not cross.county_fips.duplicated().any()
    c=c.merge(cross[['county_fips','CBSA Code','CBSA Title','Metropolitan/Micropolitan Statistical Area']],on='county_fips',how='left',validate='many_to_one')
    metro=c['Metropolitan/Micropolitan Statistical Area'].eq('Metropolitan Statistical Area')
    c['bea_geofips']=np.where(metro,c['CBSA Code'],c.state_fips+'999')
    c['geography_type']=np.where(metro,'metropolitan','state_nonmetropolitan')
    c['geography_vintage']='OMB July 2023; fixed 2024 campus county for all years'
    c['geography_source']='data/raw/census/list1_2023.xlsx'
    c=c.drop(columns=['CBSA Code','CBSA Title','Metropolitan/Micropolitan Statistical Area'])
    c.to_csv(OUT/'colleges.csv',index=False)
    hist=c[['unitid','college','usnews_rank_2026','usnews_rank_2027','ranking_source','ranking_quality']].melt(id_vars=['unitid','college','ranking_source','ranking_quality'],var_name='edition',value_name='usnews_rank')
    hist['edition']=hist.edition.str[-4:].astype(int)
    hist.to_csv(OUT/'historical_rankings.csv',index=False)
    return c

def salaries(c):
    records=[];identities=[]
    for year in sorted(int(p.name) for p in (RAW/'ipeds').iterdir() if p.name.isdigit()):
        directory=RAW/'ipeds'/str(year);p=choose(directory,'sal')
        if p is None:continue
        d=csv(p);d.columns=d.columns.str.upper();d=d[d.UNITID.isin(c.unitid)]
        hp=choose(directory,'hd') or choose(directory,'ic')
        if hp is not None:
            h=csv(hp);h.columns=h.columns.str.upper()
            if 'INSTNM' in h:
                for _,v in h[h.UNITID.isin(c.unitid)].iterrows():
                    identities.append(dict(year=year,unitid=v.UNITID,source_name=v.INSTNM,source=relative(hp)))
        drvpath=choose(directory,'drvhr');drv=None
        if drvpath:
            drv=csv(drvpath);drv.columns=drv.columns.str.upper();drv=drv.set_index('UNITID')
        if 'CONTRACT' in d:
            # Official derived equated contract rows, rather than mixing 9/10 with 11/12.
            d=d[d.CONTRACT==4]
        if 'ARANK' not in d:raise ValueError(f'Unsupported historical schema: {p}')
        d=d[d.ARANK.isin(RANKS)]
        assert not d.duplicated(['UNITID','ARANK']).any(),p
        for _,r in d.iterrows():
            rank=RANKS[int(r.ARANK)];flags=[]
            if year<2012:
                s=numeric(r.AVESALT);n=numeric(r.EMPCNTT);sv='AVESALT; CONTRACT=4';nv='EMPCNTT; CONTRACT=4';regime='pre2012_grouped_contracts';impute=str(r.get('XAVESALT',''));countflag=str(r.get('XEMPCNTT',''))
            elif year<2016:
                s=numeric(r.SAOUTLT)/numeric(r.SAMNTHT)*9 if numeric(r.SAMNTHT)>0 else np.nan
                n=numeric(r.SATOTLT);sv='9*SAOUTLT/SAMNTHT';nv='SATOTLT';regime='2012_2015_pooled_months';impute=str(r.get('XSAOUTLT',''))+'|'+str(r.get('XSAMNTHT',''));countflag=str(r.get('XSATOTLT',''))
                flags.append('pooled_months_not_identical_to_2016_method')
            else:
                s=numeric(r.SAEQ9AT);n=numeric(r.SATOTLT);sv='SAEQ9AT';nv='SATOTLT';regime='2016_onward_contract_specific';impute=str(r.get('XSAEQ9AT',''));countflag=str(r.get('XSATOTLT',''))
            salpath=p
            if drv is not None and r.UNITID in drv.index:
                var={3:'SALASST',2:'SALASSC',1:'SALPROF'}[r.ARANK]
                val=numeric(drv.loc[r.UNITID,var])
                if pd.notna(val):s=val;sv=var;salpath=drvpath
            rawsalary=s
            if n==0:s=np.nan;flags.append('zero_faculty_undefined_mean')
            if pd.isna(s):flags.append('missing_salary')
            if pd.isna(n):flags.append('missing_count')
            elif 0<n<10:flags.append('small_rank_count_lt10')
            if s==0 and n>0:flags.append('reported_zero_salary')
            if year==2024:flags.append('provisional_2024')
            if any(x not in ['R','Z','A','G','nan',''] for x in (impute+'|'+countflag).split('|')):flags.append('check_ipeds_imputation_flag')
            records.append(dict(**{f'faculty_count_{m}_month':numeric(r.get(f'SA{m:02}MCT',np.nan)) for m in [9,10,11,12]},unitid=int(r.UNITID),year=int(year),academic_year=f'{year}–{str(year+1)[-2:]}',academic_rank=rank,salary_nominal=s,faculty_count=n,faculty_count_all_contracts=numeric(r.get('SAINSTT',np.nan)),faculty_count_less_than_9_months=numeric(r.get('SA_9MCT',np.nan)),source_salary_value=rawsalary,salary_method=regime,salary_source=relative(salpath),salary_variable=sv,count_source=relative(p),count_variable=nv,source_row_key=f'UNITID={int(r.UNITID)};ARANK={int(r.ARANK)}'+(';CONTRACT=4' if year<2012 else ''),salary_imputation_flags=impute,count_imputation_flag=countflag,quality_flags=';'.join(flags)))
    from historical import early_salaries
    out=pd.DataFrame(records)
    early=early_salaries(c,set(out.year))
    out=pd.concat([out,early],ignore_index=True).sort_values(['unitid','year','academic_rank'])
    # Flag large changes and observed changes in reported months worked.
    groups=out.groupby(['unitid','academic_rank'])
    previous=groups.salary_nominal.shift(1)
    adjacent=(out.year-groups.year.shift(1)).eq(1)
    out['salary_nominal_yoy_pct']=(100*(out.salary_nominal/previous-1)).where(adjacent)
    countcols=[f'faculty_count_{m}_month' for m in [9,10,11,12]]
    out['dominant_months_worked']=out[countcols].idxmax(axis=1,skipna=True).str.extract(r'count_(\d+)_')[0].astype(float)
    oldmonths=out.groupby(['unitid','academic_rank']).dominant_months_worked.shift(1)
    changed=adjacent&oldmonths.notna()&out.dominant_months_worked.notna()&out.dominant_months_worked.ne(oldmonths)
    out.loc[changed,'quality_flags']+=';dominant_months_worked_changed'
    out.loc[out.salary_nominal_yoy_pct.abs()>20,'quality_flags']+=';salary_change_gt20pct_review'
    out.loc[out.unitid.eq(112260)&out.year.eq(2019),'quality_flags']+=';cmc_2019_all_12_month_contracts_comparability_break'
    out.to_csv(OUT/'faculty_salaries.csv',index=False)
    for ip in sorted(RAW.glob('ipeds/*/urban_directory.json')):
        payload=json.loads(ip.read_text())
        assert not payload.get('next'), 'Identity response not fully paginated'
        for v in payload.get('results',[]):
            identities.append(dict(year=v['year'],unitid=v['unitid'],source_name=v['inst_name'],source=relative(ip)))
    pd.DataFrame(identities).drop_duplicates(['unitid','year']).to_csv(OUT/'institution_identity_audit.csv',index=False)
    return out

def cost_of_living():
    parts=[]
    for folder,pattern in [('MARPP_files','MARPP_MSA*.csv'),('PARPP_files','PARPP_PORT*.csv')]:
        p=next((RAW/'bea'/folder).glob(pattern));d=csv(p)
        d=d[d.LineCode==1].copy();d['bea_geofips']=d.GeoFIPS.str.replace('"','',regex=False).str.strip().str.zfill(5)
        years=[x for x in d if re.fullmatch(r'\d{4}',x)]
        d=d.melt(id_vars=['bea_geofips','GeoName'],value_vars=years,var_name='cost_year',value_name='rpp')
        d=d.rename(columns={'GeoName':'cost_geography'});d['rpp']=pd.to_numeric(d.rpp,errors='coerce');d['cost_year']=d.cost_year.astype(int);d['rpp_source']=relative(p);d['rpp_line_code']=1
        parts.append(d)
    d=pd.concat(parts).drop_duplicates(['bea_geofips','cost_year'])
    d.to_csv(OUT/'cost_of_living.csv',index=False)
    return d

def inflation():
    p=RAW/'bea/PCEPI.csv';d=csv(p);d['year']=pd.to_datetime(d.iloc[:,0]).dt.year
    d['PCEPI']=pd.to_numeric(d.PCEPI,errors='coerce')
    g=d.groupby('year').PCEPI.agg(['mean','count']);g=g[g['count']==12].rename(columns={'mean':'pce_price_index','count':'months'})
    g['inflation_factor_2024']=g.loc[2024,'pce_price_index']/g.pce_price_index
    g['pce_source']=relative(p);g=g.reset_index();g.to_csv(OUT/'inflation.csv',index=False)
    return g

def catalog_inventory():
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin
    soup=BeautifulSoup((RAW/'ipeds/catalog.html').read_bytes(),'html.parser');rows=[]
    for tr in soup.select('tr'):
        cells=tr.find_all('td',recursive=False)
        if len(cells)<4:continue
        year=cells[0].get_text(strip=True);links=tr.select('a[href]')
        if not re.fullmatch(r'\d{4}',year) or not links:continue
        code=links[0].get_text(strip=True)
        if re.fullmatch(r'(DRVHR\d{4}|SAL(?:\d{4}|\d{2})_A(?:_1|_S)?|SAL\d{4}_IS|HD\d{4}|IC(?:\d{4}|\d{2})(?:_A)?)',code,re.I):
            rows.append(dict(year=year,code=code,description=cells[2].get_text(' ',strip=True),url=urljoin('https://nces.ed.gov/ipeds/datacenter/DataFiles.aspx?year=-1',links[0]['href'])))
    pd.DataFrame(rows).drop_duplicates().to_csv(OUT/'ipeds_catalog.csv',index=False)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    catalog_inventory()
    c=colleges();s=salaries(c);cost=cost_of_living();pce=inflation()
    # Preserve even wholly missing school-years in each recovered survey year.
    grid=pd.MultiIndex.from_product([c.unitid,sorted(s.year.unique()),list(RANKS.values())],names=['unitid','year','academic_rank']).to_frame(index=False)
    long=grid.merge(s,on=['unitid','year','academic_rank'],how='left',validate='one_to_one').merge(c,on='unitid',validate='many_to_one')
    long['academic_year']=long.year.map(lambda y:f'{y}–{str(y+1)[-2:]}')
    long['quality_flags']=long.quality_flags.fillna('missing_salary_and_count')
    long['cost_year']=long.year
    long=long.merge(cost,on=['bea_geofips','cost_year'],how='left',validate='many_to_one').merge(pce,on='year',how='left',validate='many_to_one')
    names=cost[['bea_geofips','cost_geography']].drop_duplicates().set_index('bea_geofips').cost_geography
    long['cost_geography']=long.bea_geofips.map(names)
    long.loc[long.rpp.isna(),'quality_flags']+=';rpp_unavailable'
    long.loc[long.geography_type=='state_nonmetropolitan','quality_flags']+=';state_nonmetro_proxy'
    long['salary_cost_adjusted']=long.salary_nominal/(long.rpp/100)
    long['salary_real_2024']=long.salary_nominal*long.inflation_factor_2024
    long['salary_real_cost_adjusted_2024']=long.salary_cost_adjusted*long.inflation_factor_2024
    for measure in ['nominal','cost_adjusted']:
        long[f'salary_{measure}_rank']=long.groupby(['year','academic_rank'])[f'salary_{measure}'].rank(ascending=False,method='min')
    long['salary_rank_improvement']=long.salary_nominal_rank-long.salary_cost_adjusted_rank
    long['historical_usnews_rank']=np.nan # historical editions 2026/27 are separate, not backfilled
    from housing import build_housing
    housing=build_housing()
    long=long.merge(housing,on=['unitid','year'],how='left',validate='many_to_one')
    long=long.sort_values(['unitid','year','academic_rank']);long.to_csv(OUT/'combined_long.csv',index=False)
    rankcols=['dominant_months_worked','salary_nominal_yoy_pct']+[f'faculty_count_{m}_month' for m in [9,10,11,12]]+['salary_nominal','faculty_count','faculty_count_all_contracts','faculty_count_less_than_9_months','source_salary_value','salary_method','salary_source','salary_variable','count_source','count_variable','source_row_key','salary_imputation_flags','count_imputation_flag','quality_flags','salary_cost_adjusted','salary_real_2024','salary_real_cost_adjusted_2024','salary_nominal_rank','salary_cost_adjusted_rank','salary_rank_improvement']
    base=[x for x in long if x not in rankcols+['academic_rank']]
    wide=long[base].drop_duplicates(['unitid','year']).set_index(['unitid','year'])
    for rank in RANKS.values():
        vals=long[long.academic_rank==rank].set_index(['unitid','year'])[rankcols].add_prefix(rank+'_')
        wide=wide.join(vals,validate='one_to_one')
    wide=wide.reset_index().sort_values(['year','usnews_rank_2027','college']);wide.to_csv(OUT/'combined.csv',index=False)
    from schema import write_dictionary
    write_dictionary(long,wide)
    coverage=long.groupby(['year','academic_rank']).agg(institutions=('unitid','size'),salary_observations=('salary_nominal','count'),rpp_observations=('salary_cost_adjusted','count'),rent_observations=('median_gross_rent','count')).reset_index();coverage.to_csv(OUT/'coverage.csv',index=False)
    long['all_three_available']=long.salary_nominal.notna()&long.rpp.notna()&long.median_gross_rent.notna()
    allcov=long.groupby(['year','academic_rank']).all_three_available.sum().reset_index()
    coverage.merge(allcov,on=['year','academic_rank']).to_csv(OUT/'coverage.csv',index=False)
    print(f'{c.shape[0]} colleges; {len(wide)} college-years; {long.year.min()}–{long.year.max()}')
    print(wide[wide.year==wide.year.max()].sort_values('assistant_salary_cost_adjusted_rank')[['college','assistant_salary_nominal','rpp','assistant_salary_cost_adjusted','assistant_salary_nominal_rank','assistant_salary_cost_adjusted_rank']].head(10).to_string(index=False))

if __name__=='__main__': main()
