"""Explicit adapters for archived Urban Institute mirrors of early IPEDS/HEGIS."""
import json
import numpy as np
import pandas as pd
from build_dataset import RAW, ROOT, RANKS, numeric, relative

def early_salaries(c, official_years):
    records=[]
    for path in sorted(RAW.glob('ipeds/*/urban_salary.json')):
        year=int(path.parent.name)
        if year in official_years:continue
        payload=json.loads(path.read_text())
        if payload.get('next'):raise ValueError('Unretrieved API pagination: '+str(path))
        data=pd.DataFrame(payload.get('results',[]))
        if data.empty:continue
        assert len(data)==payload['count']
        data=data[data.academic_rank.isin(RANKS)&data.unitid.isin(c.unitid)&data.sex.eq(99)]
        for (unitid,rank),g in data.groupby(['unitid','academic_rank']):
            assert not g.contract_length.duplicated().any()
            g=g.set_index('contract_length');flags=['urban_mirror_original_nces_download_failed','historical_imputation_flags_unavailable']
            if 7 in g.index:
                r=g.loc[7];s=numeric(r.average_salary);n=numeric(r.instruc_staff_count);basis='pre2012_grouped_contracts';var='average_salary; contract_length=7';key='7'
            elif 5 in g.index and 6 in g.index:
                # NCES legacy conversion: 11/12 month outlays multiplied by .8182.
                a,b=g.loc[5],g.loc[6];na,nb=numeric(a.instruc_staff_count),numeric(b.instruc_staff_count)
                oa,ob=numeric(a.salary_outlays),numeric(b.salary_outlays)
                n=na+nb;s=(oa+ob*.8182)/n if n>0 and pd.notna(oa+ob) else np.nan
                basis='pre2012_grouped_contracts';var='(outlays_contract5+.8182*outlays_contract6)/(count5+count6)';key='5,6'
                flags.append('legacy_0_8182_conversion')
            else:
                k=9 if 9 in g.index else 5 if 5 in g.index else None
                if k is None:continue
                r=g.loc[k];s=numeric(r.average_salary);n=numeric(r.instruc_staff_count)
                basis='9_month_only_early' if k==9 else '9_10_month_only_early'
                var=f'average_salary; contract_length={k}';key=str(k)
                flags.append('restricted_contract_population_not_all_9_to_12_months')
            rawsalary=s
            if n==0:s=np.nan;flags.append('zero_faculty_undefined_mean')
            if pd.isna(s):flags.append('missing_salary')
            if pd.isna(n):flags.append('missing_count')
            elif 0<n<10:flags.append('small_rank_count_lt10')
            if s==0 and n>0:flags.append('reported_zero_salary')
            records.append(dict(unitid=int(unitid),year=year,academic_year=f'{year}–{str(year+1)[-2:]}',academic_rank=RANKS[rank],salary_nominal=s,faculty_count=n,source_salary_value=rawsalary,salary_method=basis,salary_source=relative(path),salary_variable=var,count_source=relative(path),count_variable='instruc_staff_count; contract_length='+key,source_row_key=f'unitid={unitid};academic_rank={rank};sex=99;contract_length={key}',salary_imputation_flags='unavailable_in_mirror',count_imputation_flag='unavailable_in_mirror',quality_flags=';'.join(flags)))
    return pd.DataFrame(records)
