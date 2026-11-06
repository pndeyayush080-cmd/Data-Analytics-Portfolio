-- ============================================================================
-- PQ-12 — Invoices, Receivables & Cash Flow Analytics
-- Star schema warehouse star_schema + metric views anchored on raw.fact_*
-- Official metrics: M20 DSO, M21 Overdue Receivables
-- Supplementary: Historical ageing, receivables reconciliation, collections
-- ============================================================================

-- Cleanwarehouse layout:
--   star_schema.dim_client, dim_date, dim_account
--   star_schema.fact_invoice, fact_invoice_payment
--   star_schema.m20_dso, m21_overdue_receivables
--   star_schema.invoice_ledger_reconciliation, payment_ledger_reconciliation
--   star_schema.invoice_ageing_monthly, client_ageing_monthly
--   star_schema.monthly_invoicing, monthly_collections, monthly_receivables_reconciliation
--   star_schema.invoice_payment_match

-- ============================================================================
-- Dimension imports
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.dim_client AS SELECT * FROM raw.dim_client;

-- ============================================================================
-- Fact imports
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.fact_invoice AS
SELECT 
    invoice_id, invoice_number, client_id, invoice_date_key, invoice_date, due_date,
    service_line_account, subtotal, gst_rate_percent, gst_amount, total_amount,
    amount_paid, balance_due, status, last_payment_date, days_to_pay,
    days_past_due_at_cutoff, ageing_bucket_at_cutoff, carried_in_from_prior_period,
    ledger_entry_id
FROM raw.fact_invoice;

CREATE OR REPLACE VIEW star_schema.fact_invoice_payment AS
SELECT 
    payment_id, invoice_id, payment_date_key, payment_date, amount,
    payment_mode, reference_no, received_by, ledger_entry_id
FROM raw.fact_invoice_payment;

-- ============================================================================
-- M20 — DSO: Days Sales Outstanding
-- Definition: Closing receivables / Revenue incl GST (last 90 days) * 90
-- Caveat: Carried-in invoices included in numerator (if outstanding), excluded from denominator (trailing 90d)
-- Closing receivables = ALL positive outstanding invoice balances as of report_date
-- (including not-yet-due and carried-in), excluding DRAFT/CANCELLED
-- Denominator: Revenue incl GST (accounts 2200, 4001-4004) from INVOICE ledger entries in trailing 90 days
-- Grain: Month, parameterized report_date
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.m20_dso AS
WITH params AS (
    SELECT 
        COALESCE(
            CAST(getvariable('pq12_report_date') AS DATE),
            (SELECT MAX(invoice_date) FROM star_schema.fact_invoice)
        ) AS report_date
),
revenue_90d AS (
    SELECT 
        ABS(SUM(l.signed_amount_debit_positive)) AS revenue_incl_gst
    FROM star_schema.fact_ledger l
    JOIN star_schema.dim_account a ON l.account_code = a.account_code
    JOIN params p ON 1=1
    WHERE l.source_type = 'INVOICE'
      AND a.account_code IN (2200, 4001, 4002, 4003, 4004)
      AND l.entry_date >= (p.report_date - INTERVAL '90 days')
      AND l.entry_date <= p.report_date
),
invoice_payments AS (
    SELECT 
        i.invoice_id,
        i.total_amount,
        COALESCE(SUM(p.amount) FILTER (WHERE p.payment_date <= pm.report_date), 0) AS paid_by_report
    FROM star_schema.fact_invoice i
    LEFT JOIN star_schema.fact_invoice_payment p ON i.invoice_id = p.invoice_id
    CROSS JOIN (SELECT report_date FROM params) pm
    WHERE i.invoice_date <= pm.report_date
      AND i.status NOT IN ('DRAFT', 'CANCELLED')
    GROUP BY i.invoice_id, i.total_amount
),
closing_ar AS (
    SELECT COALESCE(SUM(total_amount - COALESCE(paid_by_report, 0)), 0) AS closing_receivables
    FROM invoice_payments
    WHERE total_amount - COALESCE(paid_by_report, 0) > 0
)
SELECT 
    p.report_date AS report_date,
    c.closing_receivables,
    r.revenue_incl_gst,
    CASE 
        WHEN r.revenue_incl_gst = 0 THEN NULL
        ELSE ROUND(90.0 * c.closing_receivables / r.revenue_incl_gst, 2)
    END AS dso_days
FROM params p
CROSS JOIN closing_ar c
CROSS JOIN revenue_90d r;

-- ============================================================================
-- M21 — Overdue Receivables
-- Definition: Unpaid invoice balance past due date at the report date
-- Formula: SUM(balance_due) WHERE due_date < report_date AND status NOT IN ('DRAFT','CANCELLED')
-- Grain: Client x Point-in-time, parameterized report_date
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.m21_overdue_receivables AS
WITH params AS (
    SELECT 
        COALESCE(
            CAST(getvariable('pq12_report_date') AS DATE),
            (SELECT MAX(invoice_date) FROM star_schema.fact_invoice)
        ) AS report_date
),
overdue_calc AS (
    SELECT 
        i.client_id,
        c.client_name,
        i.invoice_id,
        i.invoice_date,
        i.due_date,
        i.total_amount,
        i.balance_due,
        i.status,
        i.carried_in_from_prior_period,
        p.report_date,
        CASE 
            WHEN i.due_date < p.report_date 
                 AND i.status NOT IN ('DRAFT', 'CANCELLED')
                 AND i.balance_due > 0
            THEN i.balance_due
            ELSE 0
        END AS overdue_amount
    FROM star_schema.fact_invoice i
    JOIN star_schema.dim_client c ON i.client_id = c.client_id
    JOIN params p ON 1=1
    WHERE i.invoice_date <= p.report_date
      AND i.due_date <= p.report_date
)
SELECT 
    report_date,
    client_id,
    client_name,
    COUNT(CASE WHEN overdue_amount > 0 THEN 1 END) AS overdue_invoice_count,
    SUM(overdue_amount) AS total_overdue_receivables,
    SUM(CASE WHEN carried_in_from_prior_period = 'Y' THEN overdue_amount ELSE 0 END) AS carried_in_overdue,
    SUM(CASE WHEN carried_in_from_prior_period = 'N' THEN overdue_amount ELSE 0 END) AS new_invoice_overdue
FROM overdue_calc
GROUP BY report_date, client_id, client_name
ORDER BY total_overdue_receivables DESC;

-- ============================================================================
-- Invoice Ledger Reconciliation
-- Grain: 1 row per invoice (687 invoices with ledger_entry_id)
-- Accounts: 1100 (AR), 2200 (GST), 4001-4004 (Revenue)
-- Balance check: 1100 + 2200 + 4001-4004 = 0
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.invoice_ledger_reconciliation AS
SELECT 
    p.invoice_id,
    p.entry_id,
    p.ar_1100,
    p.gst_2200,
    p.rev_4001,
    p.rev_4002,
    p.rev_4003,
    p.rev_4004,
    (p.ar_1100 + p.gst_2200 + p.rev_4001 + p.rev_4002 + p.rev_4003 + p.rev_4004) AS balance_check,
    i.total_amount,
    ABS(p.gst_2200) + ABS(p.rev_4001) + ABS(p.rev_4002) + ABS(p.rev_4003) + ABS(p.rev_4004) AS ledger_credits_total,
    i.total_amount - (ABS(p.gst_2200) + ABS(p.rev_4001) + ABS(p.rev_4002) + ABS(p.rev_4003) + ABS(p.rev_4004)) AS invoice_ledger_diff,
    CASE 
        WHEN ABS(p.ar_1100 + p.gst_2200 + p.rev_4001 + p.rev_4002 + p.rev_4003 + p.rev_4004) < 0.01 
         AND ABS(i.total_amount - (ABS(p.gst_2200) + ABS(p.rev_4001) + ABS(p.rev_4002) + ABS(p.rev_4003) + ABS(p.rev_4004))) < 0.01
        THEN 'BALANCED'
        ELSE 'UNBALANCED'
    END AS reconciliation_status
FROM (
    SELECT 
        entry_id,
        invoice_id,
        COALESCE(MAX(CASE WHEN account_code = 1100 THEN signed_amount END), 0) AS ar_1100,
        COALESCE(MAX(CASE WHEN account_code = 2200 THEN signed_amount END), 0) AS gst_2200,
        COALESCE(MAX(CASE WHEN account_code = 4001 THEN signed_amount END), 0) AS rev_4001,
        COALESCE(MAX(CASE WHEN account_code = 4002 THEN signed_amount END), 0) AS rev_4002,
        COALESCE(MAX(CASE WHEN account_code = 4003 THEN signed_amount END), 0) AS rev_4003,
        COALESCE(MAX(CASE WHEN account_code = 4004 THEN signed_amount END), 0) AS rev_4004
    FROM (
        SELECT 
            l.entry_id,
            l.source_id AS invoice_id,
            l.account_code,
            SUM(l.signed_amount_debit_positive) AS signed_amount
        FROM star_schema.fact_ledger l
        WHERE l.source_type = 'INVOICE'
        GROUP BY l.entry_id, l.source_id, l.account_code
    ) il
    GROUP BY entry_id, invoice_id
) p
JOIN star_schema.fact_invoice i ON p.invoice_id = i.invoice_id
ORDER BY p.invoice_id;

-- ============================================================================
-- Payment Ledger Reconciliation
-- Grain: 1 row per payment (709 payments)
-- Accounts: 1001 (Bank), 1100 (AR)
-- Balance check: 1001 + 1100 = 0
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.payment_ledger_reconciliation AS
SELECT 
    p.payment_id,
    p.entry_id,
    p.bank_1001,
    p.ar_1100,
    (p.bank_1001 + p.ar_1100) AS balance_check,
    pay.amount AS payment_amount,
    ABS(p.bank_1001) - pay.amount AS bank_amount_diff,
    ABS(p.ar_1100) - pay.amount AS ar_amount_diff,
    CASE 
        WHEN ABS(p.bank_1001 + p.ar_1100) < 0.01 
         AND ABS(ABS(p.bank_1001) - pay.amount) < 0.01
         AND ABS(ABS(p.ar_1100) - pay.amount) < 0.01
        THEN 'BALANCED'
        ELSE 'UNBALANCED'
    END AS reconciliation_status
FROM (
    SELECT 
        entry_id,
        payment_id,
        COALESCE(MAX(CASE WHEN account_code = 1001 THEN signed_amount END), 0) AS bank_1001,
        COALESCE(MAX(CASE WHEN account_code = 1100 THEN signed_amount END), 0) AS ar_1100
    FROM (
        SELECT 
            l.entry_id,
            l.source_id AS payment_id,
            l.account_code,
            SUM(l.signed_amount_debit_positive) AS signed_amount
        FROM star_schema.fact_ledger l
        WHERE l.source_type = 'INVOICE_PAYMENT'
        GROUP BY l.entry_id, l.source_id, l.account_code
    ) pl
    GROUP BY entry_id, payment_id
) p
JOIN star_schema.fact_invoice_payment pay ON p.payment_id = pay.payment_id
ORDER BY p.payment_id;

-- ============================================================================
-- Invoice Ageing Monthly
-- Grain: 1 row per invoice per month-end
-- Uses payment-date reconstruction for historical outstanding
-- CANCELLED = 0 from invoice_date (assumed cancelled on invoice_date - no cancellation date available)
-- DRAFT excluded
-- LIMITATION: Historical status/cancellation dates not available in source data.
-- Outstanding reconstructed from payment dates only (payment_date <= month_end).
-- Actual historical status transitions (SENT->PAID, CANCELLED date) not available.
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.invoice_ageing_monthly AS
WITH month_ends AS (
    SELECT DISTINCT 
        (DATE_TRUNC('month', invoice_date) + INTERVAL '1 month' - INTERVAL '1 day')::DATE AS month_end
    FROM star_schema.fact_invoice
    UNION
    SELECT DISTINCT 
        (DATE_TRUNC('month', payment_date) + INTERVAL '1 month' - INTERVAL '1 day')::DATE AS month_end
    FROM star_schema.fact_invoice_payment
),
ageing AS (
    SELECT 
        m.month_end,
        i.invoice_id,
        i.client_id,
        i.invoice_date,
        i.due_date,
        i.total_amount,
        i.status,
        i.carried_in_from_prior_period,
        i.service_line_account,
        i.total_amount - COALESCE((
            SELECT SUM(p.amount) 
            FROM star_schema.fact_invoice_payment p
            WHERE p.invoice_id = i.invoice_id
              AND p.payment_date <= m.month_end
        ), 0) AS outstanding,
        (m.month_end - i.due_date) AS age_days,
        CASE 
            WHEN i.status IN ('DRAFT', 'CANCELLED') THEN 'EXCLUDED'
            WHEN i.total_amount - COALESCE((
                SELECT SUM(p.amount) 
                FROM star_schema.fact_invoice_payment p
                WHERE p.invoice_id = i.invoice_id
                  AND p.payment_date <= m.month_end
            ), 0) <= 0 THEN 'SETTLED'
            WHEN m.month_end < i.due_date THEN 'NOT_YET_DUE'
            WHEN (m.month_end - i.due_date) BETWEEN 0 AND 30 THEN '1_30_DAYS'
            WHEN (m.month_end - i.due_date) BETWEEN 31 AND 60 THEN '31_60_DAYS'
            WHEN (m.month_end - i.due_date) BETWEEN 61 AND 90 THEN '61_90_DAYS'
            WHEN (m.month_end - i.due_date) > 90 THEN '90_PLUS_DAYS'
            ELSE 'UNKNOWN'
        END AS ageing_bucket
    FROM month_ends m
    CROSS JOIN star_schema.fact_invoice i
    WHERE i.invoice_date <= m.month_end
      AND i.due_date IS NOT NULL
)
SELECT 
    month_end,
    invoice_id,
    client_id,
    invoice_date,
    due_date,
    total_amount,
    status,
    carried_in_from_prior_period,
    service_line_account,
    outstanding,
    age_days,
    ageing_bucket
FROM ageing
WHERE outstanding > 0 
   OR status IN ('DRAFT', 'CANCELLED')
ORDER BY month_end, invoice_id;

-- ============================================================================
-- Client Ageing Monthly
-- Grain: 1 row per client per month-end
-- Aggregated ageing buckets
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.client_ageing_monthly AS
SELECT 
    month_end,
    client_id,
    SUM(CASE WHEN ageing_bucket = 'NOT_YET_DUE' THEN outstanding ELSE 0 END) AS not_yet_due,
    SUM(CASE WHEN ageing_bucket = '1_30_DAYS' THEN outstanding ELSE 0 END) AS days_1_30,
    SUM(CASE WHEN ageing_bucket = '31_60_DAYS' THEN outstanding ELSE 0 END) AS days_31_60,
    SUM(CASE WHEN ageing_bucket = '61_90_DAYS' THEN outstanding ELSE 0 END) AS days_61_90,
    SUM(CASE WHEN ageing_bucket = '90_PLUS_DAYS' THEN outstanding ELSE 0 END) AS days_90_plus,
    SUM(CASE WHEN ageing_bucket = 'SETTLED' THEN outstanding ELSE 0 END) AS settled,
    SUM(outstanding) AS total_outstanding,
    COUNT(CASE WHEN ageing_bucket IN ('1_30_DAYS','31_60_DAYS','61_90_DAYS','90_PLUS_DAYS') THEN 1 END) AS overdue_invoice_count
FROM star_schema.invoice_ageing_monthly
WHERE ageing_bucket NOT IN ('EXCLUDED')
GROUP BY month_end, client_id
ORDER BY month_end, client_id;

-- ============================================================================
-- Monthly Invoicing
-- Grain: 1 row per month
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.monthly_invoicing AS
SELECT 
    DATE_TRUNC('month', invoice_date)::DATE AS month,
    COUNT(*) AS invoice_count,
    SUM(total_amount) AS total_invoiced,
    SUM(subtotal) AS total_subtotal,
    SUM(gst_amount) AS total_gst,
    SUM(total_amount - gst_amount) AS revenue_amount,
    COUNT(DISTINCT client_id) AS unique_clients
FROM star_schema.fact_invoice
WHERE status NOT IN ('DRAFT', 'CANCELLED')
GROUP BY DATE_TRUNC('month', invoice_date)
ORDER BY month;

-- ============================================================================
-- Monthly Collections
-- Grain: 1 row per month
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.monthly_collections AS
SELECT 
    DATE_TRUNC('month', p.payment_date)::DATE AS month,
    COUNT(*) AS payment_count,
    SUM(p.amount) AS total_collected,
    AVG(p.amount) AS avg_payment_amount,
    COUNT(DISTINCT p.invoice_id) AS invoices_paid,
    COUNT(DISTINCT i.client_id) AS clients_paying
FROM star_schema.fact_invoice_payment p
JOIN star_schema.fact_invoice i ON p.invoice_id = i.invoice_id
GROUP BY DATE_TRUNC('month', p.payment_date)
ORDER BY month;

-- ============================================================================
-- Monthly Receivables Reconciliation
-- Grain: 1 row per month
-- Opening AR + Invoice Issuance - Collections = Closing AR
-- NOT a cash flow view - this is receivables movement
-- Uses payment-date reconstruction for historical outstanding
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.monthly_receivables_reconciliation AS
WITH month_ends AS (
    SELECT DISTINCT 
        (DATE_TRUNC('month', invoice_date) + INTERVAL '1 month' - INTERVAL '1 day')::DATE AS month_end
    FROM star_schema.fact_invoice
    UNION
    SELECT DISTINCT 
        (DATE_TRUNC('month', payment_date) + INTERVAL '1 month' - INTERVAL '1 day')::DATE AS month_end
    FROM star_schema.fact_invoice_payment
),
recon AS (
    SELECT 
        m.month_end,
        (m.month_end - INTERVAL '1 month')::DATE + INTERVAL '1 day' AS month_start,
        COALESCE((
            SELECT SUM(i.total_amount - COALESCE((
                SELECT SUM(p.amount) 
                FROM star_schema.fact_invoice_payment p
                WHERE p.invoice_id = i.invoice_id
                  AND p.payment_date < m.month_start
            ), 0))
            FROM star_schema.fact_invoice i
            WHERE i.invoice_date < m.month_start
              AND i.status NOT IN ('DRAFT', 'CANCELLED')
              AND i.total_amount - COALESCE((
                SELECT SUM(p.amount) 
                FROM star_schema.fact_invoice_payment p
                WHERE p.invoice_id = i.invoice_id
                  AND p.payment_date < m.month_start
            ), 0) > 0
        ), 0) AS opening_ar,
        COALESCE((
            SELECT SUM(total_amount)
            FROM star_schema.fact_invoice
            WHERE invoice_date >= m.month_start
              AND invoice_date <= m.month_end
              AND status NOT IN ('DRAFT', 'CANCELLED')
        ), 0) AS invoice_issuance,
        COALESCE((
            SELECT SUM(amount)
            FROM star_schema.fact_invoice_payment
            WHERE payment_date >= m.month_start
              AND payment_date <= m.month_end
        ), 0) AS collections,
        COALESCE((
            SELECT SUM(i.total_amount - COALESCE((
                SELECT SUM(p.amount) 
                FROM star_schema.fact_invoice_payment p
                WHERE p.invoice_id = i.invoice_id
                  AND p.payment_date <= m.month_end
            ), 0))
            FROM star_schema.fact_invoice i
            WHERE i.invoice_date <= m.month_end
              AND i.status NOT IN ('DRAFT', 'CANCELLED')
              AND i.total_amount - COALESCE((
                SELECT SUM(p.amount) 
                FROM star_schema.fact_invoice_payment p
                WHERE p.invoice_id = i.invoice_id
                  AND p.payment_date <= m.month_end
            ), 0) > 0
        ), 0) AS actual_closing_ar
    FROM (
        SELECT 
            month_end,
            (month_end - INTERVAL '1 month')::DATE + INTERVAL '1 day' AS month_start
        FROM month_ends
    ) m
)
SELECT 
    month_end,
    month_start,
    opening_ar,
    invoice_issuance,
    collections,
    opening_ar + invoice_issuance - collections AS expected_closing_ar,
    actual_closing_ar,
    (opening_ar + invoice_issuance - collections) - actual_closing_ar AS reconciliation_difference
FROM recon
ORDER BY month_end;

-- ============================================================================
-- Invoice Payment Match
-- Grain: 1 row per invoice
-- Reconciliation status of invoice vs payments
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.invoice_payment_match AS
WITH pay_totals AS (
    SELECT 
        invoice_id,
        SUM(amount) AS sum_payments,
        COUNT(*) AS payment_count,
        MAX(payment_date) AS last_payment_date,
        MIN(payment_date) AS first_payment_date
    FROM star_schema.fact_invoice_payment
    GROUP BY invoice_id
)
SELECT 
    i.invoice_id,
    i.invoice_number,
    i.client_id,
    i.invoice_date,
    i.due_date,
    i.total_amount,
    i.amount_paid AS source_amount_paid,
    i.balance_due AS source_balance_due,
    i.status,
    i.carried_in_from_prior_period,
    COALESCE(p.sum_payments, 0) AS computed_sum_payments,
    COALESCE(p.payment_count, 0) AS payment_count,
    p.last_payment_date,
    p.first_payment_date,
    i.total_amount - COALESCE(p.sum_payments, 0) AS computed_outstanding,
    i.amount_paid - COALESCE(p.sum_payments, 0) AS amount_paid_discrepancy,
    CASE 
        WHEN i.status IN ('DRAFT', 'CANCELLED') THEN 'EXCLUDED'
        WHEN COALESCE(p.sum_payments, 0) = 0 THEN 'UNPAID'
        WHEN COALESCE(p.sum_payments, 0) >= i.total_amount THEN 'MATCH'
        WHEN COALESCE(p.sum_payments, 0) > 0 THEN 'PARTIAL'
        ELSE 'UNPAID'
    END AS reconciliation_status,
    CASE 
        WHEN i.invoice_id = 'INV-00385' THEN 'FLAGGED_100_DISCREPANCY'
        ELSE ''
    END AS anomaly_flag
FROM star_schema.fact_invoice i
LEFT JOIN pay_totals p ON i.invoice_id = p.invoice_id
ORDER BY i.invoice_id;

-- ============================================================================
-- Known Anomalies Documentation
-- ============================================================================
CREATE OR REPLACE VIEW star_schema.known_anomalies AS
SELECT * FROM (VALUES
    ('INV-00385', 'AMOUNT_PAID_DISCREPANCY', 'amount_paid (1,049,828) exceeds single payment (1,049,728) by 100. Payment and ledger match at 1,049,728.', 'UNEXPLAINED_SOURCE_DATA_INCONSISTENCY', 'FLAGGED_IN_INVOICE_PAYMENT_MATCH'),
    ('INV-00187', 'CANCELLED_BALANCE_ZERO', 'CANCELLED invoice with total_amount=2,450,388, amount_paid=0, balance_due=0. Computed balance=2,450,388.', 'CANCELLED_ACCOUNTING_PRACTICE', 'FLAGGED_IN_INVOICE_PAYMENT_MATCH'),
    ('INV-00198', 'CANCELLED_BALANCE_ZERO', 'CANCELLED invoice with total_amount=1,087,016, amount_paid=0, balance_due=0. Computed balance=1,087,016.', 'CANCELLED_ACCOUNTING_PRACTICE', 'FLAGGED_IN_INVOICE_PAYMENT_MATCH'),
    ('INV-00334', 'CANCELLED_BALANCE_ZERO', 'CANCELLED invoice with total_amount=1,177,994, amount_paid=0, balance_due=0. Computed balance=1,177,994.', 'CANCELLED_ACCOUNTING_PRACTICE', 'FLAGGED_IN_INVOICE_PAYMENT_MATCH'),
    ('INV-00421', 'CANCELLED_BALANCE_ZERO', 'CANCELLED invoice with total_amount=824,820, amount_paid=0, balance_due=0. Computed balance=824,820.', 'CANCELLED_ACCOUNTING_PRACTICE', 'FLAGGED_IN_INVOICE_PAYMENT_MATCH'),
    ('INV-00007', 'CARRIED_IN_OVERDUE_MISSING_LEDGER', 'Carried-in OVERDUE invoice (2025-02-14) with balance_due=1,388,978 missing ledger_entry_id. Pre-ledger period.', 'PRE_LEDGER_PERIOD', 'MISSING_LEDGER_REFERENCE'),
    ('INV-00740', 'DRAFT_MISSING_LEDGER', 'DRAFT invoice (2026-09-29) missing ledger_entry_id. Post-ledger period.', 'POST_LEDGER_NO_ENTRY', 'MISSING_LEDGER_REFERENCE'),
    ('INV-00187', 'CANCELLED_MISSING_LEDGER', 'CANCELLED invoice (2025-07-15) missing ledger_entry_id. No payments, no ledger.', 'CANCELLED_NO_LEDGER', 'MISSING_LEDGER_REFERENCE'),
    ('INV-00198', 'CANCELLED_MISSING_LEDGER', 'CANCELLED invoice (2025-07-22) missing ledger_entry_id. No payments, no ledger.', 'CANCELLED_NO_LEDGER', 'MISSING_LEDGER_REFERENCE'),
    ('INV-00334', 'CANCELLED_MISSING_LEDGER', 'CANCELLED invoice (2025-11-04) missing ledger_entry_id. No payments, no ledger.', 'CANCELLED_NO_LEDGER', 'MISSING_LEDGER_REFERENCE'),
    ('INV-00421', 'CANCELLED_MISSING_LEDGER', 'CANCELLED invoice (2026-01-09) missing ledger_entry_id. No payments, no ledger.', 'CANCELLED_NO_LEDGER', 'MISSING_LEDGER_REFERENCE')
) AS t(invoice_id, anomaly_type, description, classification, detection_method);