USE financial_performance;


-- =========================================================
-- VENDOR EXPENSE ANALYSIS
-- =========================================================

-- 1. Top 10 Vendors by Expense
SELECT
    vendor_id,
    COUNT(*) AS expense_transactions,
    SUM(ABS(amount)) AS total_expense
FROM financial_transactions
WHERE account_type = 'Expense'
  AND vendor_id IS NOT NULL
GROUP BY vendor_id
ORDER BY total_expense DESC
LIMIT 10;


-- 2. Top Vendors with Vendor Details
SELECT
    v.vendor_id,
    v.vendor_name,
    v.category,
    v.region,
    SUM(ABS(ft.amount)) AS total_expense
FROM financial_transactions ft
JOIN vendors v
    ON ft.vendor_id = v.vendor_id
WHERE ft.account_type = 'Expense'
GROUP BY
    v.vendor_id,
    v.vendor_name,
    v.category,
    v.region
ORDER BY total_expense DESC
LIMIT 10;


-- 3. Expense by Vendor Category
SELECT
    v.category,
    COUNT(DISTINCT v.vendor_id) AS vendors,
    SUM(ABS(ft.amount)) AS total_expense
FROM financial_transactions ft
JOIN vendors v
    ON ft.vendor_id = v.vendor_id
WHERE ft.account_type = 'Expense'
GROUP BY v.category
ORDER BY total_expense DESC;


-- 4. Vendor Expense by Region
SELECT
    v.region,
    COUNT(DISTINCT v.vendor_id) AS vendors,
    SUM(ABS(ft.amount)) AS total_expense
FROM financial_transactions ft
JOIN vendors v
    ON ft.vendor_id = v.vendor_id
WHERE ft.account_type = 'Expense'
GROUP BY v.region
ORDER BY total_expense DESC;


-- 5. Average Expense per Vendor by Region
SELECT
    v.region,
    COUNT(DISTINCT v.vendor_id) AS vendors,
    ROUND(
        SUM(ABS(ft.amount))
        / COUNT(DISTINCT v.vendor_id),
        2
    ) AS avg_expense_per_vendor
FROM financial_transactions ft
JOIN vendors v
    ON ft.vendor_id = v.vendor_id
WHERE ft.account_type = 'Expense'
GROUP BY v.region
ORDER BY avg_expense_per_vendor DESC;


-- 6. Top 10 Vendors by Expense with Transaction Count
SELECT
    v.vendor_id,
    v.vendor_name,
    COUNT(ft.transaction_id) AS transaction_count,
    ROUND(SUM(ABS(ft.amount)), 2) AS total_expense,
    ROUND(
        SUM(ABS(ft.amount))
        / COUNT(ft.transaction_id),
        2
    ) AS avg_expense_per_transaction
FROM financial_transactions ft
JOIN vendors v
    ON ft.vendor_id = v.vendor_id
WHERE ft.account_type = 'Expense'
GROUP BY
    v.vendor_id,
    v.vendor_name
ORDER BY total_expense DESC
LIMIT 10;


-- 7. Top 10 Vendor Expense Concentration
SELECT
    ROUND(
        SUM(total_expense)
        /
        (
            SELECT SUM(ABS(amount))
            FROM financial_transactions
            WHERE account_type = 'Expense'
        )
        * 100,
        2
    ) AS top_10_vendor_expense_pct
FROM
(
    SELECT
        vendor_id,
        SUM(ABS(amount)) AS total_expense
    FROM financial_transactions
    WHERE account_type = 'Expense'
      AND vendor_id IS NOT NULL
    GROUP BY vendor_id
    ORDER BY total_expense DESC
    LIMIT 10
) x;