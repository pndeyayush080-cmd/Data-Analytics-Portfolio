USE financial_performance;


-- =========================================================
-- CONCENTRATION ANALYSIS
-- =========================================================


-- 1. Top 10 Customers by Revenue
SELECT
    customer_id,
    COUNT(*) AS transactions,
    SUM(amount) AS total_revenue
FROM financial_transactions
WHERE account_type = 'Revenue'
  AND customer_id IS NOT NULL
GROUP BY customer_id
ORDER BY total_revenue DESC
LIMIT 10;


-- 2. Top 10 Customers with Customer Details
SELECT
    c.customer_id,
    c.customer_name,
    c.segment,
    c.region,
    COUNT(ft.transaction_id) AS transactions,
    SUM(ft.amount) AS total_revenue
FROM financial_transactions ft
JOIN customers c
    ON ft.customer_id = c.customer_id
WHERE ft.account_type = 'Revenue'
GROUP BY
    c.customer_id,
    c.customer_name,
    c.segment,
    c.region
ORDER BY total_revenue DESC
LIMIT 10;


-- 3. Top 10 Customer Revenue Concentration
SELECT
    ROUND(
        SUM(total_revenue)
        /
        (
            SELECT SUM(amount)
            FROM financial_transactions
            WHERE account_type = 'Revenue'
        )
        * 100,
        2
    ) AS top_10_customer_revenue_pct
FROM
(
    SELECT
        customer_id,
        SUM(amount) AS total_revenue
    FROM financial_transactions
    WHERE account_type = 'Revenue'
      AND customer_id IS NOT NULL
    GROUP BY customer_id
    ORDER BY total_revenue DESC
    LIMIT 10
) x;


-- 4. Top 10 Vendors by Expense
SELECT
    vendor_id,
    COUNT(*) AS transactions,
    SUM(ABS(amount)) AS total_expense
FROM financial_transactions
WHERE account_type = 'Expense'
  AND vendor_id IS NOT NULL
GROUP BY vendor_id
ORDER BY total_expense DESC
LIMIT 10;


-- 5. Top 10 Vendors with Vendor Details
SELECT
    v.vendor_id,
    v.vendor_name,
    v.category,
    v.region,
    COUNT(ft.transaction_id) AS transactions,
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


-- 6. Top 10 Vendor Expense Concentration
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