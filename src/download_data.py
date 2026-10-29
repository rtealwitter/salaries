"""Archive original responses and ZIP members; never overwrite a captured source."""
from pathlib import Path
import argparse, csv, hashlib, io, json, re, threading, zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
ROOT = Path(__file__).resolve().parents[1]
LOCK = threading.Lock()
FIELDS = ['path','url','downloaded_at_utc','coverage','description','status','http_status','bytes','sha256','archive_member']
CATALOG = 'https://nces.ed.gov/ipeds/datacenter/DataFiles.aspx?year=-1'

def fetch(url, path, coverage='', description='', kind=None):
    dest = ROOT / path
    if dest.exists():
        return dest
    row = dict.fromkeys(FIELDS, '')
    row.update(path=str(path), url=url, downloaded_at_utc=datetime.now(timezone.utc).isoformat(), coverage=coverage, description=description)
    try:
        r = requests.get(url, timeout=90)
        row['http_status'] = r.status_code
        data = r.content
        valid = r.ok
        if kind == 'zip': valid &= zipfile.is_zipfile(io.BytesIO(data))
        if kind == 'json':
            try: valid &= isinstance(r.json(), list)
            except ValueError: valid = False
        if kind == 'pdf': valid &= data.startswith(b'%PDF')
        if not valid:
            row['status'] = 'blocked_or_invalid_response'
            dest = dest.with_name(dest.name + '.response.txt')
            row['path'] = str(dest.relative_to(ROOT))
        else: row['status'] = 'ok'
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists(): dest.write_bytes(data)
        row.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        rows = [row]
        if valid and kind == 'zip':
            z = zipfile.ZipFile(io.BytesIO(data))
            for name in z.namelist():
                if name.endswith('/'): continue
                target = dest.parent / (dest.stem + '_files') / Path(name).name
                target.parent.mkdir(parents=True, exist_ok=True)
                payload = z.read(name)
                if not target.exists(): target.write_bytes(payload)
                rows.append(dict(row, path=str(target.relative_to(ROOT)), bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest(), archive_member=name))
        with LOCK:
            manifest = ROOT/'data/sources.csv'
            exists = manifest.exists()
            with manifest.open('a',newline='') as f:
                w=csv.DictWriter(f,fieldnames=FIELDS)
                if not exists:w.writeheader()
                w.writerows(rows)
        print(row['status'],path,flush=True)
        return dest if valid else None
    except requests.RequestException as e:
        row.update(status='request_error', description=description+'; '+str(e))
        with LOCK:
            manifest=ROOT/'data/sources.csv'; exists=manifest.exists()
            with manifest.open('a',newline='') as f:
                w=csv.DictWriter(f,fieldnames=FIELDS)
                if not exists:w.writeheader()
                w.writerow(row)
        print('ERROR',url,str(e),flush=True)
        return None

def download_core():
    p=fetch(CATALOG,'data/raw/ipeds/catalog.html','1980–2025','IPEDS complete data file catalog')
    soup=BeautifulSoup(p.read_bytes(),'html.parser'); jobs=[]; inventory=[]
    for tr in soup.select('tr'):
        cells=tr.find_all('td',recursive=False)
        if len(cells)<4:continue
        year=cells[0].get_text(strip=True)
        if not re.fullmatch(r'\d{4}',year):continue
        links=tr.select('a[href]')
        if not links:continue
        code=links[0].get_text(strip=True)
        desc=cells[2].get_text(' ',strip=True)
        chosen= bool(re.fullmatch(r'(DRVHR\d{4}|SAL(?:\d{4}|\d{2})_A(?:_1|_S)?|SAL\d{4}_IS|HD\d{4}|IC(?:\d{4}|\d{2})(?:_A)?)',code,re.I))
        # Historical IC files carry the identifiers and names before HD existed.
        if not chosen:continue
        inventory.append(dict(year=year,code=code,description=desc,url=urljoin(CATALOG,links[0]['href'])))
        for a in [links[0]]+[a for a in links if a.get_text(strip=True)=='Dictionary']:
            u=urljoin(CATALOG,a['href']); jobs.append((u,f'data/raw/ipeds/{year}/{u.split("/")[-1]}',year,desc,'zip'))
    (ROOT/'data/processed').mkdir(exist_ok=True)
    with (ROOT/'data/processed/ipeds_catalog.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=['year','code','description','url']);w.writeheader();w.writerows(inventory)
    jobs += [
      ('https://apps.bea.gov/regional/zip/MARPP.zip','data/raw/bea/MARPP.zip','2008–2024','Metro and state nonmetro RPPs and IRPD; February 2026 vintage','zip'),
      ('https://apps.bea.gov/regional/zip/SARPP.zip','data/raw/bea/SARPP.zip','2008–2024','State RPPs, IRPD and real personal income; February 2026 vintage','zip'),
      ('https://fred.stlouisfed.org/graph/?g=1&cosd=1959-01-01&coed=2024-12-31&id=PCEPI','data/raw/bea/pce_fred_graph.html','1959–2024','FRED PCEPI graph metadata',None),
      ('https://fred.stlouisfed.org/graph/fredgraph.csv?id=PCEPI','data/raw/bea/PCEPI.csv','1959 onward','BEA monthly PCE price index distributed by Federal Reserve Bank of St. Louis',None),
      ('https://www.bea.gov/data/prices-inflation/regional-price-parities-state-and-metro-area','data/raw/bea/rpp_page.html','2024','Release dates and RPP definitions',None),
      ('https://www.bea.gov/sites/default/files/methodologies/Methodology-for-Regional-Price-Parities_0.pdf','data/raw/bea/methodology.pdf','current','BEA RPP methodology','pdf'),
      ('https://apps.bea.gov/scb/issues/2023/04-april/0423-regional-price-parities.htm','data/raw/bea/revisions_2023.html','2017–2021','BEA RPP revisions',None),
      ('https://www.collegekickstart.com/blog/item/u-s-news-world-report-posts-2027-college-rankings','data/raw/rankings/kickstart_2027.html','2026–2027','Secondary transcription of U.S. News with previous-year ranks',None),
      ('https://www.usnews.com/best-colleges/rankings/national-liberal-arts-colleges','data/raw/rankings/usnews_2027.html','2027','Publisher ranking access attempt',None),
      ('https://www.usnews.com/education/best-colleges/articles/how-us-news-calculated-the-rankings','data/raw/rankings/methodology.html','2027','Publisher ranking methodology access attempt',None),
      ('https://data.aaup.org/ipeds-ft-faculty-salaries/','data/raw/ipeds/aaup_explorer.html','2002–2024','AAUP IPEDS salary explorer description and embedded workbook',None),
      ('https://nces.ed.gov/programs/digest/d22/app_a2_14.asp','data/raw/ipeds/methodology_history.html','historical','NCES coverage and human resources changes',None),
      ('https://files.eric.ed.gov/fulltext/ED319308.pdf','data/raw/ipeds/salaries_1977_1987.pdf','1977–1987','NCES historical salaries report; aggregate HEGIS/IPEDS history','pdf'),
    ]
    jobs=list(dict.fromkeys(jobs))
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(lambda j:fetch(*j),jobs))

def replay_manifest(include_failed=False):
    """Restore successful top-level downloads listed in the frozen manifest."""
    manifest=ROOT/'data/sources.csv'
    if not manifest.exists():
        raise SystemExit('No manifest: run --discover first, then download_housing.py.')
    with manifest.open() as f: rows=list(csv.DictReader(f))
    jobs={}
    for r in rows:
        if r['archive_member'] or not r['path'] or r['path'].endswith('.response.txt'):continue
        if r['status']!='ok' and not include_failed:continue
        path=r['path'];kind='zip' if path.lower().endswith('.zip') else 'pdf' if path.lower().endswith('.pdf') else None
        jobs[path]=(r['url'],path,r['coverage'],r['description'],kind)
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(lambda j:fetch(*j),jobs.values()))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--discover',action='store_true',help='Discover IPEDS core files from the catalog; existing raw bytes are retained.')
    parser.add_argument('--include-failed',action='store_true',help='Retry failed requests as well as successful archived URLs.')
    args=parser.parse_args()
    if args.discover:download_core()
    else:replay_manifest(args.include_failed)
