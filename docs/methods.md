# Sources, methods, and limitations

## Methods

For salary `S`, all-items RPP `R`, and the annual mean national PCE index `P`:

```text
salary_cost_adjusted            = S / (R / 100)
salary_real_2024                = S * P[2024] / P[year]
salary_real_cost_adjusted_2024  = S / (R / 100) * P[2024] / P[year]
```

The annual PCE mean uses all 12 monthly observations; incomplete years are excluded. The reference-year mean is 123.662 in the captured PCE vintage. Re-basing the price index would not change the adjustment ratio.

Academic year 2024–25 is indexed by its fall/start year, 2024, and paired with calendar-year 2024 RPP and PCE. This is a consistent alignment convention, not an exact academic-year expenditure-weighted price index. RPP describes relative prices across places in a year; changes in RPP alone are **not** local inflation. The combined PCE/RPP adjustment supplies the national time dimension, but remains an aggregate index, not each faculty member's personal cost of living.

### Salary definitions and breaks

The modern population is full-time, nonmedical instructional staff, including instruction combined with research/public service, regardless of formal faculty designation or tenure status. Benefits, outside consulting income, and an individual's total compensation are not measured.

- **1980/1984/1985:** the mirror identifies nine-month-only salaries. These are retained with `9_month_only_early`, not presented as complete 9–12-month populations.
- **Legacy grouped contracts:** use published nine-month-equivalent rows when available. Otherwise, when both 9/10- and 11/12-month categories exist, calculate `(outlays_9_10 + 0.8182*outlays_11_12) / (count_9_10 + count_11_12)`, following the archived NCES dictionary. If only the 9/10-month group is available, preserve that restricted measure with an explicit flag; do not assume an absent 11/12 group is zero.
- **2003–2011:** original SAL files, `CONTRACT=4`, `AVESALT` and `EMPCNTT`; revised `_rv` files preferred when supplied.
- **2012–2015:** `9*SAOUTLT/SAMNTHT`, with `SATOTLT` headcount. Salary outlays were pooled across contract lengths, so this is not identical to the later conversion.
- **2016 onward:** `SAEQ9AT`, with outlays separately converted by months worked. The dictionary's factors are **1, .90, .818, .75** for 9, 10, 11, 12 months. These reproduce the official means within $0.50. Use the published mean, not a newly substituted unrounded estimate.
- **2021–2024:** prefer DRVHR's `SALASST`, `SALASSC`, `SALPROF`; source headcounts from SAL. The 2024 file is provisional; earlier final/revised files are used when present.

The archive includes dictionaries for every successfully downloaded original salary file. Imputation/correction flags are retained separately from substantive values. The mirror does not preserve the original imputation flags; early rows state that limitation. National HEGIS/IPEDS survey scope and reporting changed over the long period, so this is not a perfectly homogeneous 45-year series.

### CMC's 2019–20 dip

CMC reported all three ranks as **12-month** staff in 2019, whereas 2018 and 2020 report them as **nine-month** staff. Assistant averages are $90,502, $72,306, and $92,572 in those three years. In 2019, $4,434,741 of salary outlays divided by 46 assistants is $96,407 before conversion; multiplying by .75 yields the published nine-month equivalent.

This establishes a reporting comparability break, **not a verified pay cut or a proven reporting error**. No value is corrected or imputed. The 2019 CMC observations are marked × in both historical figures and disconnected from the trend lines. The data carry `cmc_2019_all_12_month_contracts_comparability_break`, along with generic month-category-change and large-change flags. Individual raises cannot be inferred from these changing group averages.

### Geography and housing

Campus county comes from HD2024; the Census/OMB July 2023 delineation file maps that county to a metropolitan or micropolitan area. This matches the geography vintage stated in the BEA files. Use one fixed geography per college throughout the historical analysis, not changing vintage-specific metro codes.

Metropolitan colleges use MARPP. **Carleton, Colby, Grinnell, Middlebury, Bucknell, and Washington and Lee** use their state's **nonmetropolitan portion** from PARPP. Micropolitan counties count as nonmetropolitan for this purpose. They are not assigned the nearest metro, a statewide average, or a national rural average. Carleton's campus county is Rice County, which is micropolitan even though Northfield extends into another county. Vassar's current metro lacks BEA observations before 2016; no older New York metro is substituted.

Claremont is assigned the Los Angeles–Long Beach–Anaheim metro. This aggregates a very large and varied housing market. ACS table B25064 adds **median monthly gross rent and its 90% margin of error**, for explicitly mapped host cities/towns, separately from the overall adjustment. Rent includes the Census gross-rent concept and is a median across renter-occupied units paying cash rent, not the rent faced by newly hired faculty. Five-year estimates pool overlapping years and differ in housing mix; they are not annual spot-rent indexes.

For context, Claremont's 2020–2024 median is **$2,237 ± $186**, versus **$2,063 ± $6** for the Los Angeles metro in the same archived national B25064 table (`GEO_ID=310M700US31080`). These different populations and uncertainties do not establish a precise city-level all-items price premium. Haverford, Williamstown, Wellesley, Brunswick, Middlebury, Kirkland, and Poughkeepsie use explicitly identified town/township geographies where appropriate. Campus mailing city, campus footprint, and faculty residence are different concepts.

BEA's regular RPP products do not supply a comparable annual city/tract all-items index. Commerce has published [experimental county-RPP research](https://www.commerce.gov/news/blog/2024/03/estimating-county-level-regional-price-parities-public-data); this is documented as an alternative to investigate, not substituted into the official series. Commercial city indexes and housing-only measures are not interchangeable with RPP.

## Validation, discrepancies, and access limitations

The pipeline executes **33 required checks**, including every archived file's checksum, unique keys, complete grids, annual directory identity evidence, missing/zero handling, arithmetic, ranking ties, year alignment, geography coverage, salary outlay reconciliation, and figure presence. Reports preserve the underlying comparisons, not just a pass label.

- All **1,170 annual identities** reconcile, with reviewed historical abbreviations and CMC's earlier name in `config/identity_aliases.csv`.
- The Urban 2003 overlap matches all **90** original NCES college/rank salary values exactly, supporting the mirror's variable mapping. This does not prove every earlier value is error-free.
- An independent secondary display of CMC matches all three 2024 salaries and headcounts exactly. It is another presentation of IPEDS, not an independent compensation survey.
- The South Carolina Commission on Higher Education's independently published Fall 2024 table provides **12** salary/headcount comparisons at four institutions outside this cohort. Charleston and The Citadel agree in count and within $1 for all six ranks. Clemson and Coastal Carolina have six discrepancies, retained in the report; scope, less-than-nine-month staff, reporting vintage, or corrections can differ. Those discrepancies are not silently reconciled or treated as independent confirmation.
- The UNI 2025–26 factbook salary table was also archived. Its labeled 2024–25 Charleston assistant value ($78,669) matches IPEDS 2023, while the current 2024 source is $81,141; it was not used to overwrite the correctly aligned series.
- **AAUP comparison remains incomplete:** its explorer's definition and 2002–2024 coverage agree with the modern measure, but Tableau workbook and CSV requests returned HTTP 404. No numeric AAUP agreement is claimed. AAUP's separate Faculty Compensation Survey has different scope and is not substituted.
- **NCES historical originals:** after the 2003–2024 files were retrieved, numerous older archive/dictionary requests failed with connection resets; explicit retries also failed. The exact attempted URLs/errors are retained. Earlier salaries and directories come from the Urban Institute's harmonized IPEDS/HEGIS API, with original JSON responses preserved. Missing original ZIPs/dictionaries are an unresolved source-access limitation.
- **U.S. News:** direct publisher and methodology requests timed out. The cohort and 2026 comparison ranks are parsed from the archived [College Kickstart table](https://www.collegekickstart.com/blog/item/u-s-news-world-report-posts-2027-college-rankings), flagged as secondary transcription. No claim of direct publisher verification is made. That source describes 2027 adoption of the 2025 Carnegie classification and replacement of the debt metric with earnings by major. Classification changes and altered weights make historical ranks nonconstant measures; `historical_usnews_rank` is missing for the salary years, with available 2026/2027 editions stored separately.
- **Census API:** requests returned a “Missing Key” page. The pipeline recovered the full rent series from official public bulk files instead: sequence archives for 2009–2020 and table-based files for 2021–2024.

Two observed rank groups have fewer than ten staff: Harvey Mudd's assistants in 1980 (7) and associates in 1984 (8). They are flagged, not suppressed. `reports/quality_review.csv` also identifies large annual changes, imputation/correction flags, missing observations, and changes in dominant reported months worked.

This fixed modern elite-college cohort introduces selection/survivorship considerations. Rankings measure neither causal educational quality nor faculty working conditions. Discipline mix, seniority within rank, visiting appointments, benefits, teaching loads, and changes in who is employed can all affect institutional mean salaries. The analyses describe these reported means and regional purchasing power; they do not estimate individual faculty welfare or a causal effect of college rank.

## Full 30-college comparison

The README figure results use 15 schools. In the complete 30-school dataset, the latest nominal leaders are Harvey Mudd (assistant, $117,064), CMC (associate, $143,283), and Barnard (full, $211,842). Cost-adjusted leaders remain Williams ($119,469), Carleton ($145,471), and Washington and Lee ($189,689). Richmond is second for assistant salaries both nominally ($115,901) and after adjustment ($118,438).

The largest assistant rank improvements are Carleton, 20 → 5, and Grinnell, 25 → 10. The largest declines are CMC, 11 → 25, and Pomona, 5 → 18. CMC's associate and full ranks move 1 → 12 and 2 → 11. These are competition ranks within all 30 colleges, not the default plotting cohort.
