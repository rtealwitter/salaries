"""Separate ACS rent context; never used as an all-items deflator."""
from pathlib import Path
import csv as csv_module
import re
import numpy as np
import pandas as pd
from build_dataset import RAW,ROOT,OUT,numeric,relative

def normalize_geo(s):
    # Sequence files use 16000US; table-based files use 1600000US.
    return s[:3]+'0000US'+s.split('US')[1]

def build_housing():
    mapping=pd.read_csv(ROOT/'config/housing_geographies.csv');wanted=set(mapping.acs_geo_id);rows=[]
    for y in range(2009,2025):
        directory=RAW/'census'/str(y);data={}
        if y>=2021:
            p=directory/f'acsdt5y{y}-b25064.dat'
            if not p.exists():continue
            d=pd.read_csv(p,sep='|',dtype=str);d=d[d.GEO_ID.isin(wanted)]
            for _,r in d.iterrows():data[r.GEO_ID]=(r.B25064_E001,r.B25064_M001,relative(p),'GEO_ID='+r.GEO_ID,'B25064_E001;B25064_M001')
        else:
            lookup=directory/'sequence_lookup.txt'
            if not lookup.exists():continue
            d=pd.read_csv(lookup,encoding='latin1',dtype=str).rename(columns={'seq':'Sequence Number','position':'Start Position'})
            r=d[(d['Table ID']=='B25064')&d['Start Position'].notna()].iloc[0];seq=r['Sequence Number'].zfill(4);pos=int(r['Start Position'])-1
            for p in list(directory.glob(f'g{y}5*.csv'))+list(directory.glob(f'g{y}5*.txt')):
                state=p.stem[-2:];links={}
                if p.suffix=='.csv':
                    for fields in csv_module.reader(p.open(encoding='latin1')):
                        if len(fields)<5:continue
                        if fields[2] not in ['060','160'] or fields[3]!='00':continue
                        ids=[s for s in fields if re.fullmatch(r'(060|160)00US\d+',s)]
                        if not ids:continue
                        geo=normalize_geo(ids[0])
                        if geo in wanted:links[fields[4]]=geo
                else:
                    for line in p.read_text(encoding='latin1').splitlines():
                        if line[8:11] not in ['060','160'] or line[11:13]!='00':continue
                        match=re.search(r'(060|160)00US\d+',line)
                        if match:
                            geo=normalize_geo(match.group())
                            if geo in wanted:links[line[13:20]]=geo
                folder=directory/f'{y}5{state}{seq}000_files'
                ep=folder/f'e{y}5{state}{seq}000.txt';mp=folder/f'm{y}5{state}{seq}000.txt'
                if not ep.exists() or not mp.exists():continue
                vals={}
                for label,source in [('e',ep),('m',mp)]:
                    for fields in csv_module.reader(source.open(encoding='latin1')):
                        if fields[5] in links:vals.setdefault(fields[5],{})[label]=fields[pos]
                for log,v in vals.items():
                    if 'e' in v and 'm' in v:data[links[log]]=(v['e'],v['m'],relative(ep)+';'+relative(mp)+';'+relative(p),f'LOGRECNO={log};sequence={seq}',f'B25064;column_1_based={pos+1}')
        for _,m in mapping.iterrows():
            v=data.get(m.acs_geo_id);estimate=numeric(v[0]) if v else np.nan;moe=numeric(v[1]) if v else np.nan
            flags=[]
            if v is None:flags.append('geography_unavailable_no_substitution')
            elif pd.isna(estimate):flags.append('estimate_unavailable_or_suppressed')
            if pd.isna(moe):flags.append('moe_unavailable_or_special')
            if pd.notna(moe) and pd.notna(estimate) and estimate>0 and moe/estimate>.3:flags.append('relative_moe_gt30pct')
            rows.append(dict(unitid=m.unitid,year=y,acs_geo_id=m.acs_geo_id,acs_geography=m.acs_geography,acs_period=f'{y-4}–{y}',median_gross_rent=estimate,median_gross_rent_moe90=moe,rent_estimate_raw=v[0] if v else '',rent_moe_raw=v[1] if v else '',rent_source=v[2] if v else '',rent_source_row_key=v[3] if v else '',rent_variable=v[4] if v else 'B25064_001E;B25064_001M',housing_quality_flags=';'.join(flags),housing_geography_note=m.housing_geography_note))
    out=pd.DataFrame(rows);out.to_csv(OUT/'city_housing.csv',index=False);return out
if __name__=='__main__':print(build_housing().groupby('year').median_gross_rent.count())
