1. Master-table PK validation

-- Validate all master-table Primary Keys together
SELECT
    (SELECT COUNT(*) FROM customers) AS customer_rows,
    (SELECT COUNT(DISTINCT customer_id) FROM customers) AS unique_customers,

    (SELECT COUNT(*) FROM vendors) AS vendor_rows,
    (SELECT COUNT(DISTINCT vendor_id) FROM vendors) AS unique_vendors,

    (SELECT COUNT(*) FROM headcount) AS headcount_rows,
    (SELECT COUNT(DISTINCT employee_id) FROM headcount) AS unique_employees,

    (SELECT COUNT(*) FROM budget) AS budget_rows,
    (SELECT COUNT(DISTINCT CONCAT(year, '-', month, '-', business_unit)) FROM budget)
        AS unique_budget_keys;

2. Critical NULL validation

-- Check NULLs in critical transaction fields
SELECT
    SUM(transaction_id IS NULL) AS null_transaction_id,
    SUM(transaction_date IS NULL) AS null_transaction_date,
    SUM(amount IS NULL) AS null_amount,
    SUM(account_type IS NULL) AS null_account_type,
    SUM(category IS NULL) AS null_category,
    SUM(business_unit IS NULL) AS null_business_unit,
    SUM(region IS NULL) AS null_region
FROM financial_transactions;

3. Customer FK validation

SELECT COUNT(*) AS invalid_customer_ids
FROM financial_transactions ft
LEFT JOIN customers c
    ON ft.customer_id = c.customer_id
WHERE ft.customer_id IS NOT NULL
  AND c.customer_id IS NULL;

4. Vendor FK validation

SELECT COUNT(*) AS invalid_vendor_ids
FROM financial_transactions ft
LEFT JOIN vendors v
    ON ft.vendor_id = v.vendor_id
WHERE ft.vendor_id IS NOT NULL
  AND v.vendor_id IS NULL;

5. Transaction ID uniqueness

SELECT
    COUNT(*) AS total_transactions,
    COUNT(DISTINCT transaction_id) AS unique_transaction_ids
FROM financial_transactions;

6. Amount integrity

SELECT
    COUNT(*) AS total_transactions,
    SUM(amount > 0) AS positive_amounts,
    SUM(amount < 0) AS negative_amounts,
    SUM(amount = 0) AS zero_amounts
FROM financial_transactions;

7. Date-range validation

SELECT
    MIN(transaction_date) AS earliest_transaction,
    MAX(transaction_date) AS latest_transaction
FROM financial_transactions;

8. Revenue/Expense sign validation

SELECT
    SUM(account_type = 'Revenue' AND amount <= 0) AS invalid_revenue,
    SUM(account_type = 'Expense' AND amount >= 0) AS invalid_expense
FROM financial_transactions;

9. Customer/Vendor assignment logic

SELECT
    SUM(account_type = 'Revenue' AND customer_id IS NULL) AS revenue_without_customer,
    SUM(account_type = 'Expense' AND vendor_id IS NULL) AS expense_without_vendor,
    SUM(account_type = 'Revenue' AND vendor_id IS NOT NULL) AS revenue_with_vendor,
    SUM(account_type = 'Expense' AND customer_id IS NOT NULL) AS expense_with_customer
FROM financial_transactions;

10. Duplicate-record validation

SELECT
    transaction_date,
    amount,
    account_type,
    category,
    business_unit,
    region,
    customer_id,
    vendor_id,
    description,
    COUNT(*) AS duplicate_count
FROM financial_transactions
GROUP BY
    transaction_date,
    amount,
    account_type,
    category,
    business_unit,
    region,
    customer_id,
    vendor_id,
    description
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC;

11. Final transaction validation

SELECT
    COUNT(*) AS total_transactions,

    COUNT(DISTINCT transaction_id) AS unique_transactions,

    SUM(CASE
        WHEN transaction_date IS NULL THEN 1
        ELSE 0
    END) AS missing_dates,

    SUM(CASE
        WHEN amount IS NULL THEN 1
        ELSE 0
    END) AS missing_amounts

FROM financial_transactions;