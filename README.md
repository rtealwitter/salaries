# Faculty salaries and local purchasing power at top liberal arts colleges

A reproducible comparison of the **30 highest-ranked civilian colleges in the 2027 U.S. News National Liberal Arts Colleges table**, using a fixed cohort throughout history. Actual publisher ranks and ties are retained: the cohort ends with the three colleges tied at rank 31. The Naval, Military, and Air Force academies are excluded.

The **four main figures use the top 15 civilian colleges** from that dataset. This fixed plotting cohort runs through publisher rank 16, retaining all three colleges tied there. The full 30-college dataset remains available; its salary-rank columns and the results below refer to all 30. Figure salary ranks, medians, percentile bands, and relative purchasing-power premiums are recalculated within the selected 15.

**Latest common year: 2024–25 salaries and calendar-year 2024 regional prices.** The captured IPEDS catalog has HR/salary files through 2024, despite some other components extending to 2025. BEA's February 19, 2026 release supplies 2024 RPPs and revised 2008–2023 estimates. Files were retrieved October 29, 2026; exact UTC timestamps and SHA-256 checksums are in [data/sources.csv](data/sources.csv).

## Results in the latest year

These are average salaries of full-time instructional staff, not starting salaries or discipline-specific pay. Regional adjustment is sensitive to the chosen geography.

| Faculty rank | Highest nominal average | Highest cost-adjusted average |
|---|---|---|
| Assistant | Harvey Mudd: $117,064 | Williams: $119,469 |
| Associate | Claremont McKenna: $143,283 | Carleton: $145,471 |
| Full | Barnard: $211,842 | Washington and Lee: $189,689 |

Among assistant professors, Richmond is second both before ($115,901) and after adjustment ($118,438). The largest improvements are Carleton, 20 → 5, and Grinnell, 25 → 10. Washington and Lee moves 15 → 3. The largest declines are CMC, 11 → 25, and Pomona, 5 → 18. Harvey Mudd moves 1 → 11. These are competition ranks within the 30-college cohort, calculated separately for each faculty rank and year.

CMC's assistant average is $100,426 nominal and approximately $88,430 after dividing by Los Angeles–Long Beach–Anaheim's RPP of 113.566. CMC ranks 1 → 12 for associates and 2 → 11 for full professors. Rankings can amplify small dollar differences; consult the salary values as well.

## Four main figures

Following review, the original set of separate scatterplots, bars, and slope charts was condensed to **four PNG files**. All four cover assistant, associate, and full professors using the same fixed top-15 civilian cohort. Every college is labeled in the scatterplots, salary comparisons, and heatmaps. College labels repeat in each faculty-rank panel of the latter two figures because their orders differ.

The plotting cohort is Williams, Amherst, Bowdoin, CMC, Pomona, Swarthmore, Harvey Mudd, Wellesley, Vassar, Washington and Lee, Hamilton, Wesleyan, Carleton, Davidson, and Grinnell. “Top 15” counts civilian schools after excluding military academies; it does not mean publisher rank ≤15. The cohort is held fixed across years, rather than selecting the historically top-ranked schools each year. Medians and percentile bands use the available college averages in each year/rank, with equal weight per college, and include CMC. Missing observations can reduce the contributing count.

1. [Current salary comparison](figures/current_salary_comparison.png): connected nominal and adjusted dots for every college, with one column per faculty rank. Each panel is sorted independently by that rank's nominal salary, highest first, and has its own college labels. Scales differ across ranks. CMC's annotated salary ranks are within the 15-school plotting cohort.
2. [Historical salary trends](figures/historical_salary_trends.png): six panels, with faculty rank in columns and nominal versus cost-adjusted pay in rows. CMC is shown against the median and 10th–90th percentile of college means. The bottom row also adjusts for national inflation to express purchasing power in 2024 dollars. Nominal history begins in 1980; regional purchasing power begins in 2008.
3. [Relative purchasing-power trends](figures/relative_purchasing_power_trends.png): one heatmap per rank, showing every college's premium or discount relative to that year's plotting-cohort median. Each panel is sorted independently by that rank's latest nominal salary, matching the current salary comparison, with its own college labels. National inflation cancels from these within-year ratios.
4. [College rank and salary](figures/college_rank_and_salary.png): six panels, rank in columns and nominal versus cost-adjusted salary in rows; identical axes within each column, all 15 colleges labeled. Fine gray lines connect displaced labels to their dots; they do not indicate changes in rank or salary.

[figure_cohort.csv](reports/figure_cohort.csv) records the institutions used in the generated figures, and [figure_salary_ranks.csv](reports/figure_salary_ranks.csv) records their latest salaries and recalculated within-cohort ranks. Use `python src/make_figures.py --top-n 30` to regenerate the four main figures for the full dataset; rerun without that option to restore the default 15. Cutoff ties are always retained, so other requested sizes may include more than the requested number of schools.

The original chart designs remain available with `--legacy`, which writes optional PNGs for the full 30-college dataset under `figures/legacy/`, independently of `--top-n`. They are not part of the four-file main set. Pure national-inflation-adjusted trends, without regional adjustment, are included in that optional set and in the CSVs.

## Coverage actually recovered

| Source/measure | Source availability investigated | Recovered in this repository |
|---|---|---|
| Institution-level IPEDS/HEGIS salaries | Public NCES catalog begins in 1980; latest HR is 2024 | 39 survey years, 1980–2024: original NCES files for 2003–2024; Urban Institute mirror for earlier years |
| Preferred DRVHR files | DRVHR2021–2024 in captured catalog | 2021–2024; salary-component files provide the earlier observations |
| BEA all-items RPP | 2008–2024, latest February 2026 vintage | All 17 years, metro and state nonmetro series |
| BEA PCE price index via FRED | Monthly series begins January 1959 | Complete annual means for 1959–2025; analysis uses 1980–2024 |
| ACS five-year median gross rent | Five-year endpoint years 2009–2024 | All 16 endpoint years from public bulk files; 469 of 480 college-period values |
| U.S. News rankings | Annual rankings extend much further back; methodology/classifications change | 2027 fixed cohort and 2026 ranks, from a preserved secondary table; no invented earlier ranks |
| AAUP IPEDS explorer | Described coverage: Fall 2002–2024 | Description archived; numeric workbook/export access blocked |

Recovered salary years are **1980, 1984, 1985, 1987, 1989, 1990–1999, and 2001–2024**. Years absent from the catalog are not interpolated. Aggregate HEGIS/NCES publications reach earlier, but their national aggregates cannot supply missing institution-level values.

The main wide panel contains **1,170 college-year rows**; **1,168** have salaries. The long version has **3,510 college-year-rank rows**, of which **3,504** have salary values. The two missing college-years are Bowdoin in 1985 and CMC in 2002. Bowdoin's reported zero full-professor headcount is retained as zero, with its undefined mean salary left missing. There are no nonmissing zero salary means in the resulting panel.

Three distinct analysis windows are retained:

- **Nominal salaries:** the 39 years above, 1,168 observed college-years.
- **Salaries plus RPP:** 2008–2024, **502** observed college-years. Vassar's current metro has no published RPP before 2016, so its eight earlier adjustments remain missing.
- **Salaries plus RPP plus city/town rent:** 2009–2024, **462** college-years. Amherst Town city's selected geography is unavailable in the archived pre-2020 files; a different historical geography is not silently substituted. All 30 colleges have all three measures for 2020–2024.

[coverage.csv](data/processed/coverage.csv) gives year/rank counts, including component availability and the three-way intersection.

## Rebuild and verify

Tested with Python 3.9. The pinned dependencies support the environment used to generate these outputs. No API keys are needed for the captured pipeline.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Restore missing successful downloads from the frozen source manifest.
# Existing raw files are never overwritten. Skip this for a fully populated clone.
python src/download_data.py

# Entirely offline transformations, then figures and validation.
python src/build_dataset.py
python src/make_figures.py
python src/validate.py

# Optional original chart designs, PNG only.
python src/make_figures.py --legacy
```

`build_dataset.py` needs only the archived `data/raw/` files and reviewed `config/` mappings. It regenerates processed data; it does not require a network connection or a pre-existing combined CSV. `validate.py` exits nonzero on a failed required check. `reports/validation_checks.csv` and `reports/validation_summary.json` record results.

To investigate new releases, `python src/download_data.py --discover` scans the captured NCES catalog for core data/dictionaries; `python src/download_housing.py` retrieves the historical ACS sequence archives. `--include-failed` retries unsuccessful manifest URLs. The default replay covers the additional sources and fallback files already recorded in the manifest. Download discovery is not a promise that new releases have unchanged schemas.

**Updating a vintage:** preserve this repository/tag first, use a separate checkout or archive directory for a new capture, and update the catalog, year range, cohort/geography decisions, and validation expectations deliberately. Caching is intentionally immutable: rerunning against existing raw files does not silently refresh them. Upstream URLs can later serve revised bytes; exact reproduction uses the committed snapshot, not an assumption that a future download has the same checksum. Do not delete the old raw vintage to update it.

## Data files and tracing a number

- [combined.csv](data/processed/combined.csv): one row per college/year, shared location/ranking/RPP/PCE/rent fields, and `assistant_`, `associate_`, `full_` salary/count/rank/provenance fields.
- [combined_long.csv](data/processed/combined_long.csv): one row per college/year/academic rank; convenient for analysis.
- [faculty_salaries.csv](data/processed/faculty_salaries.csv): observed salary rows, source variables, headcounts and reporting flags.
- [cost_of_living.csv](data/processed/cost_of_living.csv): all-items RPP by BEA geography/year, from MARPP and PARPP.
- [inflation.csv](data/processed/inflation.csv), [city_housing.csv](data/processed/city_housing.csv), [colleges.csv](data/processed/colleges.csv), and [historical_rankings.csv](data/processed/historical_rankings.csv): separate reusable components.
- [data_dictionary.csv](data/processed/data_dictionary.csv): meanings and units of processed columns.
- [institution_identity_audit.csv](data/processed/institution_identity_audit.csv): annual directory evidence for the UNITIDs.

For example, filter long data to `unitid=112260`, `year=2024`, `academic_rank=assistant`. Its `salary_source` points to the archived DRVHR CSV, `salary_variable=SALASST`; its `count_source` points to SAL2024_IS and `source_row_key` identifies `ARANK=3`. The value is $100,426 for 52 staff. The RPP row is `GeoFIPS=31080`, `LineCode=1`, column `2024`. Each relative raw path resolves to a URL, retrieval timestamp, checksum, and, where relevant, ZIP member in `sources.csv`. ZIPs and extracted member bytes are both preserved, unmodified.

Blank numeric CSV cells mean missing, not zero. `faculty_count` is the denominator corresponding to the salary measure, normally staff working 9–12 months; additional columns preserve all-contract, less-than-nine-month, and individual month-category counts where available. Parent/child allocation can affect derived IPEDS data generally; within this cohort all 360 DRVHR rank observations reconcile exactly to their salary-detail rows.

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

This establishes a reporting comparability break, **not a verified pay cut or a proven reporting error**. No value is corrected or imputed. The 2019 CMC points are hollow and disconnected in the trend chart; heatmap cells are marked ×. The data carry `cmc_2019_all_12_month_contracts_comparability_break`, along with generic month-category-change and large-change flags. Individual raises cannot be inferred from these changing group averages.

### Geography and housing

Campus county comes from HD2024; the Census/OMB July 2023 delineation file maps that county to a metropolitan or micropolitan area. This matches the geography vintage stated in the BEA files. Use one fixed geography per college throughout the historical analysis, not changing vintage-specific metro codes.

Metropolitan colleges use MARPP. **Carleton, Colby, Grinnell, Middlebury, Bucknell, and Washington and Lee** use their state's **nonmetropolitan portion** from PARPP. Micropolitan counties count as nonmetropolitan for this purpose. They are not assigned the nearest metro, a statewide average, or a national rural average. Carleton's campus county is Rice County, which is micropolitan even though Northfield extends into another county. Vassar's current metro lacks BEA observations before 2016; no older New York metro is substituted.

Claremont is assigned the Los Angeles–Long Beach–Anaheim metro. This aggregates a very large and varied housing market. ACS table B25064 adds **median monthly gross rent and its 90% margin of error**, for explicitly mapped host cities/towns, separately from the overall adjustment. Rent includes the Census gross-rent concept and is a median across renter-occupied units paying cash rent, not the rent faced by newly hired faculty. Five-year estimates pool overlapping years and differ in housing mix; they are not annual spot-rent indexes.

For context, Claremont's 2020–2024 median is **$2,237 ± $186**, versus **$2,063 ± $6** for the Los Angeles metro in the same archived national B25064 table (`GEO_ID=310M700US31080`). These different populations and uncertainties do not establish a precise city-level all-items price premium. Haverford, Williamstown, Wellesley, Brunswick, Middlebury, Kirkland, and Poughkeepsie use explicitly identified town/township geographies where appropriate. Campus mailing city, campus footprint, and faculty residence are different concepts.

BEA's regular RPP products do not supply a comparable annual city/tract all-items index. Commerce has published [experimental county-RPP research](https://www.commerce.gov/news/blog/2024/03/estimating-county-level-regional-price-parities-public-data); this is documented as an alternative to investigate, not substituted into the official series. Commercial city indexes and housing-only measures are not interchangeable with RPP.

## Validation, discrepancies, and access limitations

The pipeline executes **31 required checks**, including every archived file's checksum, unique keys, complete grids, annual directory identity evidence, missing/zero handling, arithmetic, ranking ties, year alignment, geography coverage, salary outlay reconciliation, and figure presence. Reports preserve the underlying comparisons, not just a pass label.

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
