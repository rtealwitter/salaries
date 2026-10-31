# Faculty salaries and purchasing power

A reproducible comparison of faculty pay at highly ranked U.S. liberal arts colleges. The dataset retains **30 civilian colleges and 39 survey years, 1980–2024**. The four figures use the **top 15 civilian colleges in the captured 2027 U.S. News table**, held fixed throughout history. Assistant, associate, and full professors are analyzed separately.

The latest common observation is **academic year 2024–25 salaries paired with calendar-year 2024 prices**. These are institutional averages, not starting salaries, individual raises, or discipline-specific compensation. Benefits are excluded.

## Reproduce the analysis

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/download_data.py    # Restore missing source files; optional for a full clone.
python src/build_dataset.py    # Rebuild all processed CSVs offline.
python src/make_figures.py     # Generate the four PNGs and audit their text layout.
python src/validate.py         # Check data, provenance, arithmetic, and figure outputs.
```

Use `python src/make_figures.py --top-n 30` for the full dataset; rerun without that option to restore the default 15. Cutoff ties are retained. Python 3.9 was used for this capture.

## Data sources

| Source | Recovered coverage | Use and qualifications |
|---|---|---|
| NCES IPEDS/HEGIS faculty salaries | 39 survey years, 1980–2024 | Original NCES salary files for 2003–2024; Urban Institute mirror for earlier years because older NCES downloads failed. Preferred DRVHR files cover 2021–2024. |
| BEA Regional Price Parities | 2008–2024 | All-items metro and state nonmetro RPPs; February 19, 2026 vintage. |
| BEA PCE price index, via FRED | Complete annual means, 1959–2025 | National inflation adjustment to 2024 dollars, using all 12 monthly observations. |
| U.S. News, via College Kickstart | 2027 selection and separate 2026 ranks | Archived secondary transcription; direct publisher access timed out. Actual ranks and ties are preserved. |
| Census ACS median gross rent | Five-year periods ending 2009–2024 | B25064 estimates and 90% margins of error for host cities/towns. Separate housing context, not an overall price adjustment. |

Original ZIPs, CSVs, API responses, dictionaries, and methodological references are preserved in `data/raw/`. [sources.csv](data/sources.csv) records URLs, retrieval dates, coverage, access failures, and SHA-256 checksums. The snapshot was captured October 29, 2026. The downloader refuses to save changed upstream bytes over this vintage.

Recovered salary years are 1980, 1984, 1985, 1987, 1989, 1990–1999, and 2001–2024. The 30-school panel contains **1,170 college-years**, of which **1,168 have salaries**. Bowdoin 1985 and CMC 2002 lack salary means. Salary-plus-RPP coverage is **502 college-years, 2008–2024**; adding city rent yields **462, 2009–2024**. Earlier salary observations remain available even without RPP or rent. [coverage.csv](data/processed/coverage.csv) gives the annual counts.

## How the sources are combined

1. **Fix the colleges.** Exclude the three military academies, select civilian colleges by their published 2027 rank, and retain cutoff ties. The full dataset ends at rank 31. The plotted 15 end at rank 16: Carleton, Davidson, and Grinnell are tied there. Selection does not change year by year.
2. **Join salaries by UNITID, year, and faculty rank.** Annual institution names are checked against IPEDS directories and reviewed historical aliases. Use nine-month-equivalent means and matching headcounts; prefer DRVHR where available. Preserve missing values, genuine zero counts, original variables, row keys, and quality flags.
3. **Assign regional prices.** Map each campus's 2024 county through the July 2023 OMB geography definitions, using that fixed geography for every year. Metropolitan campuses use their BEA metro RPP. Nonmetropolitan campuses use their state's nonmetro portion, not the nearest metro or the statewide average. Match the academic year's start year to the RPP calendar year.
4. **Adjust salaries.** For nominal salary `S`, RPP `R` (U.S. = 100), and annual PCE index `P`, calculate:

   ```text
   Regional purchasing power = S / (R / 100)
   Salary in 2024 dollars    = S × P[2024] / P[year]
   Both adjustments         = S / (R / 100) × P[2024] / P[year]
   ```

5. **Calculate comparisons within the selected cohort.** Salary ranks use descending competition ranks; ties share the best position. Historical medians and 10th–90th percentiles give each college equal weight, include CMC, and omit missing observations. Figure ranks are recalculated for the plotted 15; the main CSV rank columns refer to all 30. ACS rent is joined by explicitly reviewed city/town identifiers and kept separate.

RPP is a spatial price index: its change alone is **not local inflation**. Metro averages also cannot capture individual housing costs or faculty residence. Claremont uses the large Los Angeles–Long Beach–Anaheim metro. Vassar's selected metro has no RPP before 2016. Early salary contract populations vary, with conversion-method changes in 2012 and 2016. See [methods and source limitations](docs/methods.md) for the exact historical definitions and geographic decisions.

## Reading the four figures

All results below refer to the **15-school plotting cohort**. School labels repeat across the three rank columns because the orders differ. The comparison and heatmaps are independently sorted by each faculty rank's **2024 nominal salary**, highest first.

### 1. Current salary comparison

[Open the figure](figures/current_salary_comparison.png). Hollow dots show nominal salary; filled dots show purchasing power after regional adjustment. The connecting segment shows the adjustment for the same college. Each column has its own dollar scale. The red annotation gives CMC's nominal → cost-adjusted salary rank within the 15-school cohort; 1st is highest.

| Faculty rank | Highest nominal salary | Highest cost-adjusted salary | CMC: nominal → adjusted rank |
|---|---|---|---|
| Assistant | Harvey Mudd, $117,064 | Williams, $119,469 | 8 → 15 |
| Associate | CMC, $143,283 | Carleton, $145,471 | 1 → 8 |
| Full | CMC, $192,382 | Washington and Lee, $189,689 | 1 → 7 |

Regional prices materially change the ordering. For assistants, Carleton rises from 13th to 3rd, Grinnell from 15th to 6th, and Washington and Lee from 10th to 2nd. Pomona falls from 3rd to 11th. CMC's $100,426 assistant average becomes approximately $88,430 after dividing by the Los Angeles metro RPP of 113.566. Small dollar differences can produce ranking changes; the dots retain those magnitudes.

### 2. Historical salary trends

[Open the figure](figures/historical_salary_trends.png). Columns are faculty ranks. The row headings distinguish **nominal salary in dollars of each year** from **cost-adjusted salary in 2024 dollars**, which accounts for both regional prices and national inflation. CMC is red; the blue line and band show the cohort median and 10th–90th percentiles. The bottom row starts in 2008 because RPP starts then.

Nominal growth does not necessarily preserve purchasing power. From **2018 to 2024**, CMC's nominal averages rose **11.0% for assistants, 18.3% for associates, and 12.7% for full professors**. After both adjustments, the corresponding changes were **−10.5%, −4.6%, and −9.1%**. These compare changing institutional rank groups, not the same individuals.

**× marks CMC's 2019 reporting break.** All three ranks were reported as 12-month staff in 2019, versus nine-month staff in 2018 and 2020. The nine-month conversion creates the conspicuous dip. It is not a verified pay cut or a proven reporting error. The reported values remain in the data and are disconnected from the CMC trend lines. Dotted vertical lines mark the 2012/2016 conversion changes.

### 3. Relative purchasing-power trends

[Open the figure](figures/relative_purchasing_power_trends.png). Each cell shows `100 × (college adjusted salary / cohort median − 1)` for that year and faculty rank. Red means above the median; blue means below. Gray means unavailable. The × again marks CMC's 2019 reporting break.

CMC's assistant purchasing power was **2.7% below the median in 2018 and 13.0% below in 2024**. Its associates were at the median in 2024; full professors were essentially at the median (0.03% above). Washington and Lee, Carleton, and Grinnell have substantial positive premiums in several rank/year combinations. This is relative position, not absolute growth: a college can remain near the median while purchasing power falls across the group. Early missing RPP values can change the contributing cohort.

### 4. College rank and salary

[Open the figure](figures/college_rank_and_salary.png). Columns are faculty ranks; rows compare nominal and cost-adjusted salaries using identical axes within each column. Lower U.S. News ranks are better, so the highest-ranked colleges are on the left. Fine gray lines connect displaced names to their dots; they do not show changes over time.

Nominal salaries generally decline as the published college rank increases within this selected group. After regional adjustment, that pattern is much weaker: Carleton (published rank 16) leads associate purchasing power, and Washington and Lee (rank 12) leads full-professor purchasing power. The plot is descriptive; the small, selected sample and differences in faculty composition do not support a causal claim about college ranking and compensation.

## Files and checks

- **Analysis:** [combined.csv](data/processed/combined.csv) has one college-year per row; [combined_long.csv](data/processed/combined_long.csv) adds a row per faculty rank. [data_dictionary.csv](data/processed/data_dictionary.csv) describes every column. Component CSVs retain salaries, prices, inflation, rent, rankings, identities, and coverage separately.
- **Figures:** [figure_cohort.csv](reports/figure_cohort.csv) and [figure_salary_ranks.csv](reports/figure_salary_ranks.csv) identify the plotted sample and latest values. [figure_layout_audit.json](reports/figure_layout_audit.json) checks all visible text at export resolution and records the resulting PNG hashes.
- **Validation:** [validation_summary.json](reports/validation_summary.json) and [validation_checks.csv](reports/validation_checks.csv) summarize checks; the other report CSVs retain the supporting comparisons and quality flags. No exploratory logs or old chart sets are needed.
- **Code:** the four entry points above call small modules for shared file readers, early salary definitions, Census rent, column documentation, plotting style, and layout checks.

**Current validation: 33 checks passed, zero failed.** Checks cover source hashes, identities, year alignment, formulas, ranks, missing/zero handling, DRVHR against salary-detail files, independent published values, figure cohorts, and text layout. All 12 processed CSVs match the captured checksums after the offline rebuild. **Incomplete verification remains explicit:** direct U.S. News access failed; AAUP's numerical exports returned HTTP 404; older original NCES files could not be recovered; six external South Carolina salary/count comparisons disagree and remain documented. See [the detailed validation notes](docs/methods.md#validation-discrepancies-and-access-limitations) before presenting.

For a new data vintage, preserve this snapshot, archive the new originals and their metadata in `data/sources.csv`, then update the source adapters and year/cohort assumptions deliberately. The downloader restores this captured vintage; it does not silently replace it with newer data.
