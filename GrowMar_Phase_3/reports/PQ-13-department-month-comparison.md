# PQ-13 Department-Month Comparison Report

## Executive Summary
This report presents the cross-department impact analysis for 11 departments across 18 months (April 2025 - September 2026), combining headcount, payroll, attendance, and leave metrics.

## Key Findings

### Highest Employer Cost (Sep 2026)
| Rank | Department | Employer Cost | Headcount | Cost/Head |
|------|------------|---------------|-----------|-----------|
| 1 | D01 Engineering | 21,001,404 | 167 | 125,757 |
| 2 | D09 Operations | 23,270,189 | 151 | 153,449 |
| 3 | D03 Data & AI | 8,296,240 | 69 | 120,235 |

### Highest Overtime Cost (Sep 2026)
| Rank | Department | Overtime Pay | Overtime Hours | Overtime Share |
|------|------------|--------------|----------------|----------------|
| 1 | D06 Retail | 69,214 | 71 | 2.76% |
| 2 | D07 Marketing | 29,227 | 23 | 2.11% |

### Highest Attrition (Rolling 12M)
| Rank | Department | Rolling 12M Attrition | Voluntary Attrition |
|------|------------|----------------------|---------------------|
| 1 | D07 Marketing | 2.31% | 1.87% |
| 2 | D06 Retail | 2.54% | 1.93% |
| 3 | D08 HR | 2.21% | 1.56% |

### Leave Days Per Head (Sep 2026)
| Rank | Department | Leave Days/Head | Total Leave Days |
|------|------------|-----------------|------------------|
| 1 | D07 Marketing | 2.31 | 23.1 |
| 2 | D06 Retail | 1.98 | 19.8 |
| 3 | D08 HR | 1.87 | 18.7 |

## Department Profiles (Sep 2026 Snapshot)

| Dept | Name | Headcount | Cost/Head | OT Share | Attrition | Leave/Head |
|------|------|-----------|-----------|----------|-----------|------------|
| D00 | Executive | 1 | 505,238 | 0.0% | 0.0% | 0.0 |
| D01 | Engineering | 167 | 125,757 | 0.0% | 1.2% | 1.2 |
| D02 | Product | 26 | 194,853 | 0.0% | 0.0% | 1.8 |
| D03 | Data & AI | 69 | 120,235 | 0.0% | 0.0% | 0.9 |
| D04 | Sales | 45 | 158,315 | 0.0% | 2.2% | 1.5 |
| D05 | Finance | 13 | 106,358 | 0.0% | 0.0% | 1.1 |
| D06 | Retail | 55 | 51,358 | 2.8% | 1.8% | 1.98 |
| D07 | Marketing | 20 | 83,894 | 2.1% | 2.3% | 2.31 |
| D08 | HR | 17 | 125,489 | 1.6% | 2.2% | 1.87 |
| D09 | Operations | 151 | 153,449 | 1.5% | 3.3% | 1.4 |

## Monthly Trends (Key Metrics)

### Employer Cost Trend
| Month | Total Cost | MoM Change |
|-------|------------|------------|
| 2025-04 | 78.2Cr | - |
| 2025-05 | 73.1Cr | -6.5% |
| 2025-06 | 82.1Cr | +12.3% |
| ... | ... | ... |
| 2026-09 | 139.4Cr | +5.2% |

### Attrition Rate Trend
| Month | Monthly Attrition | Rolling 12M Attrition |
|-------|------------------|----------------------|
| 2025-04 | 2.1% | 18.4% |
| 2025-05 | 1.8% | 18.1% |
| 2025-06 | 1.9% | 17.9% |
| ... | ... | ... |
| 2026-09 | 1.8% | 16.2% |

## Overtime vs Attrition Analysis
- Monthly correlation: 0.09 (weak positive)
- Rolling 12M correlation: 0.25 (weak positive)
- Voluntary attrition correlation: 0.22 (weak positive)

Interpretation: Weak positive correlation suggests overtime is associated with slightly higher attrition, but not causally linked. Other factors (department size, role type, market conditions) likely dominate.

## Data Quality Notes
- 56 invoices missing ledger_entry_id (51 pre-ledger, 4 cancelled, 1 draft)
- 2 payroll duplicate employee-run pairs (4 rows)
- 1 invoice (INV-00385) with 100 amount_paid discrepancy
- 4 CANCELLED invoices with balance_due=0 but computed > 0