USE financial_performance;


-- Region-wise Financial Performance
SELECT
    region,
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
GROUP BY region
ORDER BY net_result DESC;


-- Region Net Margin
SELECT
    region,
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
GROUP BY region
ORDER BY net_margin_percent DESC;


-- Revenue by Region
SELECT
    region,
    COUNT(*) AS revenue_transactions,
    SUM(amount) AS total_revenue
FROM financial_transactions
WHERE account_type = 'Revenue'
GROUP BY region
ORDER BY total_revenue DESC;


-- Region Yearly Revenue
SELECT
    region,
    YEAR(transaction_date) AS year,
    SUM(amount) AS total_revenue
FROM financial_transactions
WHERE account_type = 'Revenue'
GROUP BY region, YEAR(transaction_date)
ORDER BY region, year;


-- Region Revenue Growth
SELECT
    region,
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
        region,
        YEAR(transaction_date) AS year,
        SUM(amount) AS total_revenue
    FROM financial_transactions
    WHERE account_type = 'Revenue'
    GROUP BY region, YEAR(transaction_date)
) x
GROUP BY region
ORDER BY revenue_growth_pct DESC;


-- Region Profit
SELECT
    region,
    SUM(CASE
        WHEN account_type = 'Revenue' THEN amount
        WHEN account_type = 'Expense' THEN amount
        ELSE 0
    END) AS total_profit
FROM financial_transactions
GROUP BY region
ORDER BY total_profit DESC;


-- Profit Margin by Region
SELECT
    region,
    ROUND(
        (
            SUM(CASE
                WHEN account_type = 'Revenue' THEN amount
                ELSE 0
            END)
            -
            SUM(CASE
                WHEN account_type = 'Expense' THEN ABS(amount)
                ELSE 0
            END)
        )
        /
        SUM(CASE
            WHEN account_type = 'Revenue' THEN amount
            ELSE 0
        END)
        * 100,
        2
    ) AS profit_margin_pct
FROM financial_transactions
GROUP BY region
ORDER BY profit_margin_pct DESC;