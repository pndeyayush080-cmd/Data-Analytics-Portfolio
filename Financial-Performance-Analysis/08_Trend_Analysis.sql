USE financial_performance;


-- =========================================================
-- TREND ANALYSIS
-- =========================================================


-- 1. Monthly Revenue Trend
SELECT
    YEAR(transaction_date) AS year,
    MONTH(transaction_date) AS month,
    SUM(amount) AS total_revenue
FROM financial_transactions
WHERE account_type = 'Revenue'
GROUP BY
    YEAR(transaction_date),
    MONTH(transaction_date)
ORDER BY
    year,
    month;


-- 2. Monthly Expense Trend
SELECT
    YEAR(transaction_date) AS year,
    MONTH(transaction_date) AS month,
    SUM(ABS(amount)) AS total_expense
FROM financial_transactions
WHERE account_type = 'Expense'
GROUP BY
    YEAR(transaction_date),
    MONTH(transaction_date)
ORDER BY
    year,
    month;


-- 3. Monthly Profit
SELECT
    YEAR(transaction_date) AS year,
    MONTH(transaction_date) AS month,

    SUM(CASE
        WHEN account_type = 'Revenue' THEN amount
        WHEN account_type = 'Expense' THEN amount
        ELSE 0
    END) AS monthly_profit

FROM financial_transactions

GROUP BY
    YEAR(transaction_date),
    MONTH(transaction_date)

ORDER BY
    year,
    month;


-- 4. Monthly Profit Margin
SELECT
    YEAR(transaction_date) AS year,
    MONTH(transaction_date) AS month,

    ROUND(
        SUM(CASE
            WHEN account_type = 'Revenue' THEN amount
            WHEN account_type = 'Expense' THEN amount
            ELSE 0
        END)
        /
        NULLIF(
            SUM(CASE
                WHEN account_type = 'Revenue' THEN amount
                ELSE 0
            END),
            0
        )
        * 100,
        2
    ) AS profit_margin_pct

FROM financial_transactions

GROUP BY
    YEAR(transaction_date),
    MONTH(transaction_date)

ORDER BY
    year,
    month;


-- 5. Year-over-Year Revenue Growth
SELECT
    year,
    yearly_revenue
FROM
(
    SELECT
        YEAR(transaction_date) AS year,
        SUM(amount) AS yearly_revenue
    FROM financial_transactions
    WHERE account_type = 'Revenue'
    GROUP BY YEAR(transaction_date)
) x
ORDER BY year;


-- 6. Year-over-Year Revenue Growth %
SELECT
    ROUND(
        (
            MAX(CASE WHEN year = 2023 THEN yearly_revenue END)
            -
            MAX(CASE WHEN year = 2022 THEN yearly_revenue END)
        )
        /
        NULLIF(
            MAX(CASE WHEN year = 2022 THEN yearly_revenue END),
            0
        )
        * 100,
        2
    ) AS revenue_growth_pct
FROM
(
    SELECT
        YEAR(transaction_date) AS year,
        SUM(amount) AS yearly_revenue
    FROM financial_transactions
    WHERE account_type = 'Revenue'
    GROUP BY YEAR(transaction_date)
) x;


-- 7. Highest Revenue Months
SELECT
    YEAR(transaction_date) AS year,
    MONTH(transaction_date) AS month,
    SUM(amount) AS total_revenue
FROM financial_transactions
WHERE account_type = 'Revenue'
GROUP BY
    YEAR(transaction_date),
    MONTH(transaction_date)
ORDER BY total_revenue DESC
LIMIT 5;


-- 8. Lowest Revenue Months
SELECT
    YEAR(transaction_date) AS year,
    MONTH(transaction_date) AS month,
    SUM(amount) AS total_revenue
FROM financial_transactions
WHERE account_type = 'Revenue'
GROUP BY
    YEAR(transaction_date),
    MONTH(transaction_date)
ORDER BY total_revenue ASC
LIMIT 5;


-- 9. Business Unit Yearly Revenue
SELECT
    business_unit,
    YEAR(transaction_date) AS year,
    SUM(amount) AS total_revenue
FROM financial_transactions
WHERE account_type = 'Revenue'
GROUP BY
    business_unit,
    YEAR(transaction_date)
ORDER BY
    business_unit,
    year;


-- 10. Business Unit Revenue Growth
SELECT
    business_unit,

    ROUND(
        (
            MAX(CASE WHEN year = 2023 THEN total_revenue END)
            -
            MAX(CASE WHEN year = 2022 THEN total_revenue END)
        )
        /
        NULLIF(
            MAX(CASE WHEN year = 2022 THEN total_revenue END),
            0
        )
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
    GROUP BY
        business_unit,
        YEAR(transaction_date)
) x

GROUP BY business_unit

ORDER BY revenue_growth_pct DESC;


-- 11. Region Yearly Revenue
SELECT
    region,
    YEAR(transaction_date) AS year,
    SUM(amount) AS total_revenue
FROM financial_transactions
WHERE account_type = 'Revenue'
GROUP BY
    region,
    YEAR(transaction_date)
ORDER BY
    region,
    year;


-- 12. Region Revenue Growth
SELECT
    region,

    ROUND(
        (
            MAX(CASE WHEN year = 2023 THEN total_revenue END)
            -
            MAX(CASE WHEN year = 2022 THEN total_revenue END)
        )
        /
        NULLIF(
            MAX(CASE WHEN year = 2022 THEN total_revenue END),
            0
        )
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
    GROUP BY
        region,
        YEAR(transaction_date)
) x

GROUP BY region

ORDER BY revenue_growth_pct DESC;