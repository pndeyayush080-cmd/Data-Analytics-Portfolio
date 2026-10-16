-- Performance by Business Unit
SELECT
    business_unit,
    SUM(CASE
        WHEN account_type = 'Revenue' THEN amount
        ELSE 0
    END) AS revenue,
    SUM(CASE
        WHEN account_type = 'Expense' THEN amount
        ELSE 0
    END) AS expense,
    SUM(CASE
        WHEN account_type IN ('Revenue', 'Expense') THEN amount
        ELSE 0
    END) AS net_result
FROM financial_transactions
GROUP BY business_unit
ORDER BY net_result DESC;


-- Business Unit Net Margin
SELECT
    business_unit,
    ROUND(
        SUM(CASE
            WHEN account_type IN ('Revenue', 'Expense') THEN amount
            ELSE 0
        END)
        /
        SUM(CASE
            WHEN account_type = 'Revenue' THEN amount
            ELSE 0
        END) * 100,
        2
    ) AS net_margin_percent
FROM financial_transactions
GROUP BY business_unit
ORDER BY net_margin_percent DESC;


-- Revenue by Business Unit
SELECT
    business_unit,
    COUNT(*) AS revenue_transactions,
    SUM(amount) AS total_revenue
FROM financial_transactions
WHERE account_type = 'Revenue'
GROUP BY business_unit
ORDER BY total_revenue DESC;


-- Average Revenue per Transaction
SELECT
    business_unit,
    ROUND(AVG(amount), 2) AS avg_revenue_per_transaction
FROM financial_transactions
WHERE account_type = 'Revenue'
GROUP BY business_unit
ORDER BY avg_revenue_per_transaction DESC;


-- Revenue Category by Business Unit
SELECT
    business_unit,
    category,
    SUM(amount) AS revenue
FROM financial_transactions
WHERE account_type = 'Revenue'
GROUP BY
    business_unit,
    category
ORDER BY
    business_unit,
    revenue DESC;


-- Business Unit Yearly Revenue
SELECT
    business_unit,
    YEAR(transaction_date) AS year,
    SUM(amount) AS total_revenue
FROM financial_transactions
WHERE account_type = 'Revenue'
GROUP BY business_unit, YEAR(transaction_date)
ORDER BY business_unit, year;


-- Business Unit Revenue Growth
SELECT
    business_unit,
    ROUND(
        (
            MAX(CASE WHEN year = 2023 THEN total_revenue END)
            -
            MAX(CASE WHEN year = 2022 THEN total_revenue END)
        )
        /
        MAX(CASE WHEN year = 2022 THEN total_revenue END)
        * 100,
        2
    ) AS revenue_growth_pct
FROM
(
    SELECT
        business_unit,
        YEAR(transaction_date) AS year,
        SUM(amount) AS total_revenue
    FROM financial_transactions
    WHERE account_type = 'Revenue'
    GROUP BY business_unit, YEAR(transaction_date)
) x
GROUP BY business_unit
ORDER BY revenue_growth_pct DESC;


-- Business Unit Profit
SELECT
    business_unit,
    SUM(CASE
        WHEN account_type = 'Revenue' THEN amount
        WHEN account_type = 'Expense' THEN amount
        ELSE 0
    END) AS total_profit
FROM financial_transactions
GROUP BY business_unit
ORDER BY total_profit DESC;


-- Business Unit Profit Margin
SELECT
    business_unit,
    ROUND(
        SUM(CASE
            WHEN account_type = 'Revenue' THEN amount
            WHEN account_type = 'Expense' THEN amount
            ELSE 0
        END)
        /
        SUM(CASE
            WHEN account_type = 'Revenue' THEN amount
            ELSE 0
        END)
        * 100,
        2
    ) AS profit_margin_pct
FROM financial_transactions
GROUP BY business_unit
ORDER BY profit_margin_pct DESC;