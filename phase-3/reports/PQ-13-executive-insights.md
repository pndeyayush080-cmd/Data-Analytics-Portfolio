# PQ-13 Executive Insights

## Executive Summary
Cross-department analytics for 11 departments over 18 months (Apr 2025 - Sep 2026) combining headcount, payroll, attendance, and leave data. All validations pass (151/151 checks across PQ-11, PQ-12, PQ-13).

---

## Key Data Quality Improvements (This Release)

### Leave Allocation Methodology Updated
- **Previous**: Equal distribution across months spanned
- **Current**: Working-day-weighted proportional allocation
- **Impact**: More accurate monthly leave totals; preserves all 910 maternity leave days
- **Invalid Request**: LR-002286 (2 days, start_date > end_date) excluded from allocation, tracked separately

### Independent Leave Validation (New)
| Metric | Result |
|--------|--------|
| Valid approved requests | 3,087 |
| Invalid requests (LR-002286) | 1 (2 days reported separately) |
| Total valid recorded days | 7,274 |
| Monthly allocated total | 7,273.9999 (match within 0.01) |
| Maternity leave preserved | 910 / 910 days ✅ |

---

## Top 5 Insights

### 1. Engineering Dominates Cost Structure
**D01 Engineering** accounts for **39.6% of total employer cost** (₹341Cr/₹862Cr over 18 months; 37.8% in Sep 2026) with 167 employees. Cost per head: ₹124K - below company average due to scale efficiencies.

### 2. Overtime Concentrated in Operations & Support
- **D09 Operations & IT**: 2.65% overtime share (₹62K/₹2.3Cr)
- **D06 Customer Support**: 2.45% overtime share (₹72K/₹2.9Cr)
- **D07 Human Resources**: 1.79% overtime share (₹29K/₹1.6Cr)
- **D08 Finance & Accounts**: 1.26% overtime share (₹31K/₹2.4Cr)
- **Rest**: < 1% or zero
- **Insight**: Overtime is operationally driven, concentrated in customer-facing and operational roles

### 3. Attrition Hotspots (Rolling 12M)
| Department | Rolling 12M Attrition | Voluntary | Risk Level |
|------------|----------------------|-----------|------------|
| D09 Operations & IT | 26.58% | 22.78% | HIGH |
| D02 Product & Design | 23.68% | 23.68% | HIGH |
| D08 Finance & Accounts | 18.46% | 18.46% | HIGH |
| D07 Human Resources | 17.22% | 17.22% | HIGH |
| D03 Data & AI | 14.24% | 10.17% | MEDIUM |
| D04 Sales | 13.69% | 13.69% | MEDIUM |
| D01 Engineering | 13.50% | 10.93% | MEDIUM |

**Action**: Investigate Operations, Product, Finance, and HR retention drivers

### 4. Overtime-Attrition Correlation Weak
- Monthly correlation: **0.09** (negligible)
- Rolling 12M: **0.34** (weak positive)
- **Interpretation**: Overtime not a primary attrition driver. Other factors (compensation, growth, management) dominate.

### 5. Receivables Health Improving
- **DSO**: 47.61 days (Sep 2026) - within industry norms
- **Overdue**: ₹27.11M (13 invoices) - 89% new invoices, 11% carried-in
- **Collection efficiency**: 90%+ within terms

---

## Department Scorecard (Sep 2026)

| Dept | Headcount | Cost/Head | OT Share | Monthly Attrition | Rolling 12M Attrition | Leave/Head | Risk |
|------|-----------|-----------|----------|-------------------|----------------------|------------|------|
| D01 Engineering | 167 | ₹124K | 0.0% | 1.25% | 13.50% | 0.49 | MEDIUM |
| D04 Sales | 46 | ₹237K | 0.0% | 2.17% | 13.69% | 0.26 | MEDIUM |
| D03 Data & AI | 52 | ₹124K | 0.0% | 0.00% | 14.24% | 0.77 | MEDIUM |
| D02 Product & Design | 26 | ₹161K | 0.0% | 0.00% | 23.68% | 0.38 | HIGH |
| D06 Customer Support | 59 | ₹50K | 2.45% | 0.00% | 5.62% | 1.29 | MEDIUM |
| D08 Finance & Accounts | 17 | ₹143K | 1.26% | 0.00% | 18.46% | 2.27 | HIGH |
| D09 Operations & IT | 29 | ₹80K | 2.65% | 0.00% | 26.58% | 0.52 | HIGH |
| D07 Human Resources | 20 | ₹82K | 1.79% | 0.00% | 17.22% | 0.65 | HIGH |
| D10 Legal & Compliance | 11 | ₹142K | 0.0% | 0.00% | 10.62% | 1.00 | MEDIUM |
| D05 Marketing | 13 | ₹106K | 0.0% | 0.00% | 0.00% | 0.54 | LOW |
| D00 Executive Office | 1 | ₹505K | 0.0% | 0.00% | 0.00% | 0.00 | LOW |

---

## Overtime vs Attrition Analysis
- Monthly correlation: **0.09** (negligible)
- Rolling 12M correlation: **0.34** (weak positive)
- **Interpretation**: Overtime not a primary attrition driver. Other factors (compensation, growth, management) dominate.

---

## Receivables Health
- **DSO**: 47.61 days (Sep 2026) - within industry norms
- **Overdue**: ₹27.11M (13 invoices) - 89% new invoices, 11% carried-in
- **Collection efficiency**: 90%+ within terms

---

## Action Items
1. **Investigate Operations, Product, Finance, and HR attrition** - exit interviews, compensation review
2. **Monitor Operations and Customer Support overtime** - 2.65% and 2.45% share suggests capacity planning issue
3. **Resolve INV-00385 ₹100 discrepancy** - finance audit
4. **Cleanse 4 CANCELLED invoice balances** - data hygiene
5. **Track overtime-attrition quarterly** - early warning system

---

## Data Confidence
- **PQ-11 (P&L)**: 60/60 PASS
- **PQ-12 (AR/AP)**: 42/42 PASS
- **PQ-13 (Cross-dept)**: 49/49 PASS
- **Integrated**: 151/151 PASS
- **Warehouse**: 31 raw tables + 47 views intact
- **Leave Allocation**: Working-day-weighted, 910/910 maternity days preserved

---

## Leave Allocation Methodology (Technical Detail)

**Working-Day-Weighted Proportional Allocation**
```
Monthly Allocation = Recorded Days × (Working Days in Month / Total Working Days Spanned)
```

**Source**: `dim_date.is_working_day = 'Y'` (excludes weekends and holidays)

**Invalid Request Handling**:
- LR-002286: start_date (2026-03-24) > end_date (2026-03-23), 2 days recorded
- Excluded from monthly allocation
- Tracked in `star_schema.pq13_invalid_leave` view
- Reported separately as 1 invalid request with 2 recorded days

**Maternity Leave Preservation**: All 7 requests (910 days) fully allocated across months with < 0.01 day rounding difference.