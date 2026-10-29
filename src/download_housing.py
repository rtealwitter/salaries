"""Recover pre-table-based ACS B25064 via public sequence files, without an API key."""
import sys
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin
from pathlib import Path
import pandas as pd
from bs4 import BeautifulSoup
from download_data import fetch, ROOT
STATES={'06':('California','ca'),'09':('Connecticut','ct'),'19':('Iowa','ia'),'23':('Maine','me'),'25':('Massachusetts','ma'),'27':('Minnesota','mn'),'36':('NewYork','ny'),'37':('NorthCarolina','nc'),'39':('Ohio','oh'),'42':('Pennsylvania','pa'),'50':('Vermont','vt'),'51':('Virginia','va')}

def year_jobs(y):
    base=f'https://www2.census.gov/programs-surveys/acs/summary_file/{y}/'
    suffix='documentation/5_year/user_tools/' if y<=2012 else 'documentation/user_tools/'
    p=fetch(base+suffix,f'data/raw/census/{y}/documentation_index.html',str(y),'Census sequence documentation directory')
    if not p:return []
    links=BeautifulSoup(p.read_bytes(),'html.parser').select('a[href]')
    candidates=[a['href'] for a in links if 'lookup' in a['href'].lower() and a['href'].lower().endswith('.txt') and not any(t in a['href'].lower() for t in ['1yr','3yr'])]
    if len(candidates)!=1:
        print('LOOKUP UNRESOLVED',y,candidates);return []
    p=fetch(urljoin(base+suffix,candidates[0]),f'data/raw/census/{y}/sequence_lookup.txt',f'{y-4}–{y}','Original ACS sequence-table lookup')
    d=pd.read_csv(p,encoding='latin1',dtype=str);d.columns=d.columns.str.strip();d=d.rename(columns={'seq':'Sequence Number','position':'Start Position'})
    row=d[(d['Table ID']=='B25064')&d['Start Position'].notna()].iloc[0]
    seq=str(row['Sequence Number']).zfill(4)
    jobs=[]
    for state,(dirname,abbr) in STATES.items():
        folder=f'data/5_year_seq_by_state/{dirname}/All_Geographies_Not_Tracts_Block_Groups/'
        for file in [f'{y}5{abbr}{seq}000.zip',f'g{y}5{abbr}.txt' if y==2009 else f'g{y}5{abbr}.csv']:
            jobs.append((base+folder+file,f'data/raw/census/{y}/{file}',f'{y-4}–{y}',f'ACS B25064 sequence {seq}, start position {row["Start Position"]}; {dirname}', 'zip' if file.endswith('.zip') else None))
    return jobs

def main():
    jobs=[]
    for y in range(2009,2021):jobs+=year_jobs(y)
    with ThreadPoolExecutor(max_workers=6) as p:list(p.map(lambda j:fetch(*j),jobs))
if __name__=='__main__':main()
