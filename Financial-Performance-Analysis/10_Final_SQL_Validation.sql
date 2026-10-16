USE financial_performance;


-- =========================================================
-- FINAL SQL VALIDATION & RECONCILIATION
-- =========================================================


-- 1. Final Transaction Count and Unique Transaction IDs
SELECT
    COUNT(*) AS total_transactions,
    COUNT(DISTINCT transaction_id) AS unique_transaction_ids
FROM financial_transactions;


-- 2. Check Missing Critical Transaction Fields
SELECT
    SUM(transaction_id IS NULL) AS null_transaction_id,
    SUM(transaction_date IS NULL) AS null_transaction_date,
    SUM(amount IS NULL) AS null_amount,
    SUM(account_type IS NULL) AS null_account_type,
    SUM(category IS NULL) AS null_category,
    SUM(business_unit IS NULL) AS null_business_unit,
    SUM(region IS NULL) AS null_region
FROM financial_transactions;


-- 3. Validate Customer Foreign Keys
SELECT
    COUNT(*) AS invalid_customer_ids
FROM financial_transactions ft
LEFT JOIN customers c
    ON ft.customer_id = c.customer_id
WHERE ft.customer_id IS NOT NULL
  AND c.customer_id IS NULL;


-- 4. Validate Vendor Foreign Keys
SELECT
    COUNT(*) AS invalid_vendor_ids
FROM financial_transactions ft
LEFT JOIN vendors v
    ON ft.vendor_id = v.vendor_id
WHERE ft.vendor_id IS NOT NULL
  AND v.vendor_id IS NULL;


-- 5. Validate Master-Table Primary Keys
SELECT
    (SELECT COUNT(*) FROM customers) AS customer_rows,
    (SELECT COUNT(DISTINCT customer_id) FROM customers) AS unique_customers,

    (SELECT COUNT(*) FROM vendors) AS vendor_rows,
    (SELECT COUNT(DISTINCT vendor_id) FROM vendors) AS unique_vendors,

    (SELECT COUNT(*) FROM headcount) AS headcount_rows,
    (SELECT COUNT(DISTINCT employee_id) FROM headcount) AS unique_employees,

    (SELECT COUNT(*) FROM budget) AS budget_rows,
    (SELECT COUNT(
        DISTINCT CONCAT(year, '-', month, '-', business_unit)
    ) FROM budget) AS unique_budget_keys;


-- 6. Validate Revenue and Expense Sign Consistency
SELECT
    SUM(account_type = 'Revenue' AND amount <= 0) AS invalid_revenue,
    SUM(account_type = 'Expense' AND amount >= 0) AS invalid_expense
FROM financial_transactions;


-- 7. Validate Customer/Vendor Assignment Logic
SELECT
    SUM(
        account_type = 'Revenue'
        AND customer_id IS NULL
    ) AS revenue_without_customer,

    SUM(
        account_type = 'Expense'
        AND vendor_id IS NULL
    ) AS expense_without_vendor,

    SUM(
        account_type = 'Revenue'
        AND vendor_id IS NOT NULL
    ) AS revenue_with_vendor,

    SUM(
        account_type = 'Expense'
        AND customer_id IS NOT NULL
    ) AS expense_with_customer

FROM financial_transactions;


-- 8. Overall Financial Reconciliation
SELECT
    SUM(
        CASE
            WHEN account_type = 'Revenue'
            THEN amount
            ELSE 0
        END
    ) AS total_revenue,

    SUM(
        CASE
            WHEN account_type = 'Expense'
            THEN ABS(amount)
            ELSE 0
        END
    ) AS total_expense,

    SUM(
        CASE
            WHEN account_type = 'Revenue'
            THEN amount
            WHEN account_type = 'Expense'
            THEN amount
            ELSE 0
        END
    ) AS total_profit

FROM financial_transactions;


-- 9. Overall Profit Margin Reconciliation
SELECT
    ROUND(
        SUM(
            CASE
                WHEN account_type = 'Revenue'
                THEN amount
                WHEN account_type = 'Expense'
                THEN amount
                ELSE 0
            END
        )
        /
        NULLIF(
            SUM(
                CASE
                    WHEN account_type = 'Revenue'
                    THEN amount
                    ELSE 0
                END
            ),
            0
        )
        * 100,
        2
    ) AS overall_profit_margin_pct

FROM financial_transactions;


-- 10. Validate Transaction Date Range
SELECT
    MIN(transaction_date) AS earliest_transaction,
    MAX(transaction_date) AS latest_transaction
FROM financial_transactions;


-- 11. Validate Foreign-Key Definitions
SELECT
    TABLE_NAME,
    COLUMN_NAME,
    CONSTRAINT_NAME,
    REFERENCED_TABLE_NAME,
    REFERENCED_COLUMN_NAME
FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA = 'financial_performance'
  AND REFERENCED_TABLE_NAME IS NOT NULL
ORDER BY
    TABLE_NAME,
    CONSTRAINT_NAME;


-- 12. Final Database Table Check
SHOW TABLES;