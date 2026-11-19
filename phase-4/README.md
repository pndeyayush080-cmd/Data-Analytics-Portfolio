# Aura Workforce Phase 4 — Automated Report Builder

Production-quality automated monthly report builder for PulseIQ workforce analytics. Generates professional PDF executive reports and Excel workbooks from the Phase 3 data warehouse.

## Features

- **Professional PDF Executive Report** — Cover page, table of contents, KPI dashboard, monthly trends with **charts**, overdue receivables, DSO detail, revenue & profit breakdown
- **Multi-sheet Excel Workbook** — KPI Summary, Monthly Trends (18 months) with **charts**, Overdue Receivables, DSO Detail, Revenue & Profit
- **Selectable Reporting Month** — Generate reports for any month from April 2025 to September 2026
- **Data Cut-off Date** — Reports show "Data as of September 30, 2026" on cover page and every page footer
- **Automated Validation** — Cross-checks against verified September 2026 values, data consistency checks
- **One-Command Execution** — Single CLI command with configurable options
- **Clean-Machine Testing** — Run from CSV snapshot without Phase 3 database (`--snapshot-dir`)
- **Scheduled Automation** — GitHub Actions workflow for monthly report generation
- **Pinned Dependencies** — Exact versions in `requirements.txt` for reproducibility
- **Comprehensive Tests** — 20 tests covering data fetching, report building, PDF/Excel generation, validation

## Quick Start

### Prerequisites

- Python 3.11+
- Required packages (auto-installed via `requirements.txt`):
  - duckdb, pandas, openpyxl, reportlab, pytest

### Installation

```bash
cd phase-4
pip install -r requirements.txt
```

### Generate September 2026 Report (Verified)

Run from the **project root directory** (`Data-Analytics-Portfolio`):

```bash
python phase-4/src/report_builder.py --month 2026-09
```

**Output:**
```
✅ Report generated successfully for September 2026
📁 Output files:
  PDF: reports/pulseiq_executive_report_2026_09.pdf
  EXCEL: reports/pulseiq_executive_report_2026_09.xlsx
🔍 Validation: PASSED
   September 2026 verified: YES
```

## Usage

### CLI Options

```bash
python phase-4/src/report_builder.py [OPTIONS]

Options:
  --month, -m TEXT       Report month (e.g., 2026-09, "September 2026", 202609) [required unless --list-months]
  --format, -f CHOICE    Output formats: pdf, excel (default: both)
  --list-months, -l      List available reporting months and exit
  --skip-validation      Skip data validation (faster)
  --db-path PATH         Path to DuckDB database (default: auto-detected)
  --snapshot-dir PATH    Path to CSV snapshot directory (for clean-machine testing)
  --output-dir PATH      Output directory for reports (default: reports)
  --log-dir PATH         Log directory (default: logs)
  --verbose, -v          Verbose logging
  --help                 Show this message and exit
```

### Examples

```bash
# Generate both PDF and Excel for September 2026
python phase-4/src/report_builder.py --month 2026-09

# Generate only PDF for April 2025
python phase-4/src/report_builder.py --month "April 2025" --format pdf

# Generate only Excel for June 2026 with verbose logging
python phase-4/src/report_builder.py --month 2026-06 --format excel --verbose

# List all available months
python phase-4/src/report_builder.py --list-months

# Skip validation for faster generation
python phase-4/src/report_builder.py --month 2026-09 --skip-validation

# Custom output directory
python phase-4/src/report_builder.py --month 2026-09 --output-dir ./my_reports

# Clean-machine mode (run from CSV snapshot without Phase 3 database)
python phase-4/create_snapshot.py --output-dir snapshot
python phase-4/src/report_builder.py --month 2026-09 --snapshot-dir snapshot
```

### Supported Month Formats

- `2026-09` (YYYY-MM)
- `2026-09-01` (YYYY-MM-DD)
- `September 2026` (Month name)
- `Sep 2026` (Abbreviated month)
- `202609` (YYYYMM)

### Available Reporting Period

April 2025 – September 2026 (18 months)

## Output Structure

### PDF Report (`pulseiq_executive_report_YYYY_MM.pdf`)

1. **Cover Page** — Report metadata, classification, disclaimer
2. **Table of Contents**
3. **Executive Summary** — Key highlights for the reporting month
4. **KPI Dashboard** — 8 KPI cards with current value, trend vs prior month, target status
5. **Monthly Trends (18 Months)** — Full history table for all KPIs
6. **Overdue Receivables Detail** — Client-level overdue breakdown (Sept 2026 only)
7. **DSO Detail** — Days Sales Outstanding calculation (Sept 2026 only)
8. **Revenue & Profit Detail** — Current month breakdown + historical revenue

### Excel Workbook (`pulseiq_executive_report_YYYY_MM.xlsx`)

| Sheet | Description |
|-------|-------------|
| **KPI Summary** | Current vs previous month, % change, target status, direction |
| **Monthly Trends** | 18-month pivot table for all 8 KPIs + **line charts** |
| **Overdue Receivables** | Client-level detail with carried/new overdue split |
| **DSO Detail** | DSO calculation components (Sept 2026 only) |
| **Revenue & Profit** | Current month P&L + historical revenue |

### PDF Report Charts

The Monthly Trends section includes two line charts:
1. **Financial KPI Trends** — Revenue, Net Profit, Operating Margin
2. **Operational KPI Trends** — Total Headcount, Rolling 12M Attrition, Attendance Rate, Overtime Share

### Excel Report Charts

The Monthly Trends sheet includes two embedded line charts matching the PDF charts.

## Scheduled Automation (GitHub Actions)

A GitHub Actions workflow (`.github/workflows/monthly-report.yml`) is included for automated monthly report generation:

- **Schedule:** Runs on the 1st of every month at 6:00 UTC
- **Manual trigger:** Can be run on-demand with `workflow_dispatch`
- **Artifacts:** PDF and Excel reports uploaded as artifacts (90-day retention)
- **Release integration:** On version tags, reports attached to GitHub Release

To enable:
1. Push the workflow file to your repository
2. (Optional) Add `DUCKDB_PATH` secret for database access
3. Reports will be generated automatically each month

## Data Source

All data sourced from `phase-3/data/warehouse/pulseiq_clean.duckdb` (read-only):

- **Primary:** `star_schema.pq15_company_scorecard` — 18 months of 8 KPIs
- **Trends:** `star_schema.pq15_kpi_trends` — Long-form KPI time series
- **Targets:** `star_schema.pq15_kpi_targets_company` — Currently all "Not Set"
- **Overdue:** `star_schema.m21_overdue_receivables` — Client-level (Sept 2026 only)
- **DSO:** `star_schema.m20_dso` — DSO calculation (Sept 2026 only)
- **Detail views:** `m16_revenue`, `m17_net_profit`, `m18_operating_margin`

## Verified September 2026 Values

| KPI | Verified Value | Report Output |
|-----|----------------|---------------|
| Revenue | ₹80,268,200 | ✅ Match |
| Net Profit | ₹14,985,979.13 | ✅ Match |
| Operating Margin | 18.67% | ✅ Match |
| DSO | 47.61 days | ✅ Match |
| Headcount | 441 | ✅ Match |
| Rolling 12M Attrition | 13.877% | ✅ Match |
| Attendance Rate | 95.187% | ✅ Match |
| Overtime Share | 0.3476% | ✅ Match |

## Data Rules

- **DSO** only available for September 2026 (earlier months show N/A)
- **Overdue Receivables** only available for September 2026
- **KPI Targets** currently "Not Set" for all metrics
- **NULL values** preserved as "N/A" — never replaced with zero
- **Read-only database access** — no modifications to source data

## Running Tests

```bash
cd phase-4
python -m pytest tests/test_report_builder.py -v
```

**Expected:** 20 tests pass covering:
- Data fetcher (connection, scorecard, trends, targets, overdue, DSO, formatting)
- Month parsing (various formats, invalid input)
- Report builder (available months, validation, data fetching)
- PDF generation (file creation, size)
- Excel generation (file creation, sheets, content verification)
- Validation (file existence, content, data consistency, Sept 2026 verified)
- End-to-end (full report build for Sept 2026 and Apr 2025)

## Project Structure

```
phase-4/
├── src/
│   ├── data_fetcher.py      # Database queries (read-only) + CSV snapshot support
│   ├── pdf_generator.py     # ReportLab PDF generation with charts
│   ├── excel_generator.py   # OpenPyXL Excel generation with charts
│   ├── validation.py        # Report validation logic
│   └── report_builder.py    # Main orchestrator + CLI
├── tests/
│   ├── conftest.py          # Pytest configuration
│   └── test_report_builder.py  # 20 comprehensive tests
├── reports/                 # Generated output (gitignored)
├── logs/                    # Execution logs (gitignored)
├── snapshot/                # CSV data snapshot (gitignored, created by create_snapshot.py)
├── create_snapshot.py       # Export DB to CSV for clean-machine testing
├── requirements.txt         # Python dependencies (pinned versions)
└── README.md               # This file
```

## Architecture Notes

- **Modular design** — Separate modules for data, PDF, Excel, validation
- **Dependency injection** — Database path configurable, defaults to auto-detection
- **Context managers** — Database connections properly closed
- **Logging** — File + console logging with timestamps
- **Error handling** — Clear error messages with actionable guidance
- **No external API calls** — Fully self-contained, works offline

## Troubleshooting

### "Cannot open database file"
Run from the **project root directory** (`Data-Analytics-Portfolio`), not from `phase-4/`:
```bash
# Correct
python phase-4/src/report_builder.py --month 2026-09

# Incorrect (from phase-4/)
python src/report_builder.py --month 2026-09
```

### Module import errors
Ensure you're using Python from the same environment where packages were installed:
```bash
python -m pip install -r phase-4/requirements.txt
```

### Permission errors on Windows
Run terminal as Administrator or use a writable output directory:
```bash
python phase-4/src/report_builder.py --month 2026-09 --output-dir %TEMP%\reports
```

## License

Internal use only — PulseIQ Workforce Analytics Platform