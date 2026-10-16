-- Revenue vs Expense by Year
SELECT
    YEAR(transaction_date) AS year,
    SUM(CASE
        WHEN account_type = 'Revenue' THEN amount
        ELSE 0
    END) AS total_revenue,
    SUM(CASE
        WHEN account_type = 'Expense' THEN amount
        ELSE 0
    END) AS total_expense,
    SUM(CASE
        WHEN account_type IN ('Revenue', 'Expense') THEN amount
        ELSE 0
    END) AS net_financial_result
FROM financial_transactions
GROUP BY YEAR(transaction_date)
ORDER BY year;


-- Year-over-Year Growth
WITH yearly AS (
    SELECT
        YEAR(transaction_date) AS year,
        SUM(CASE
            WHEN account_type = 'Revenue' THEN amount
            ELSE 0
        END) AS revenue,
        SUM(CASE
            WHEN account_type = 'Expense' THEN ABS(amount)
            ELSE 0
        END) AS expense,
        SUM(CASE
            WHEN account_type IN ('Revenue', 'Expense') THEN amount
            ELSE 0
        END) AS net_result
    FROM financial_transactions
    GROUP BY YEAR(transaction_date)
)
SELECT
    year,
    revenue,
    expense,
    net_result,
    ROUND(
        (revenue - LAG(revenue) OVER (ORDER BY year))
        / LAG(revenue) OVER (ORDER BY year) * 100,
        2
    ) AS revenue_growth_pct,
    ROUND(
        (expense - LAG(expense) OVER (ORDER BY year))
        / LAG(expense) OVER (ORDER BY year) * 100,
        2
    ) AS expense_growth_pct,
    ROUND(
        (net_result - LAG(net_result) OVER (ORDER BY year))
        / LAG(net_result) OVER (ORDER BY year) * 100,
        2
    ) AS net_result_growth_pct
FROM yearly
ORDER BY year;


-- Monthly Financial Trend
SELECT 
    YEAR(transaction_date) AS year,
    MONTH(transaction_date) AS month,
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
GROUP BY YEAR(transaction_date), MONTH(transaction_date)
ORDER BY year, month;


-- Best Performing Months
SELECT
    YEAR(transaction_date) AS year,
    MONTH(transaction_date) AS month,
    SUM(amount) AS net_result
FROM financial_transactions
WHERE account_type IN ('Revenue', 'Expense')
GROUP BY
    YEAR(transaction_date),
    MONTH(transaction_date)
ORDER BY net_result DESC
LIMIT 5;


-- Worst Performing Months
SELECT
    YEAR(transaction_date) AS year,
    MONTH(transaction_date) AS month,
    SUM(amount) AS net_result
FROM financial_transactions
WHERE account_type IN ('Revenue', 'Expense')
GROUP BY
    YEAR(transaction_date),
    MONTH(transaction_date)
ORDER BY net_result ASC
LIMIT 5;


-- Monthly Revenue Trend
SELECT
    YEAR(transaction_date) AS year,
    MONTH(transaction_date) AS month,
    SUM(amount) AS revenue
FROM financial_transactions
WHERE account_type = 'Revenue'
GROUP BY
    YEAR(transaction_date),
    MONTH(transaction_date)
ORDER BY
    year,
    month;


-- Monthly Revenue: 2022 vs 2023
SELECT
    MONTH(transaction_date) AS month,
    SUM(CASE
        WHEN YEAR(transaction_date) = 2022 THEN amount
        ELSE 0
    END) AS revenue_2022,
    SUM(CASE
        WHEN YEAR(transaction_date) = 2023 THEN amount
        ELSE 0
    END) AS revenue_2023
FROM financial_transactions
WHERE account_type = 'Revenue'
GROUP BY MONTH(transaction_date)
ORDER BY month;


-- Monthly Revenue Growth %
SELECT
    MONTH(transaction_date) AS month,
    ROUND(
        (
            SUM(CASE
                WHEN YEAR(transaction_date) = 2023 THEN amount
                ELSE 0
            END)
            -
            SUM(CASE
                WHEN YEAR(transaction_date) = 2022 THEN amount
                ELSE 0
            END)
        )
        /
        SUM(CASE
            WHEN YEAR(transaction_date) = 2022 THEN amount
            ELSE 0
        END)
        * 100,
        2
    ) AS growth_percent
FROM financial_transactions
WHERE account_type = 'Revenue'
GROUP BY MONTH(transaction_date)
ORDER BY month;


-- Yearly Revenue
SELECT
    year,
    SUM(total_revenue) AS yearly_revenue
FROM
(
    SELECT
        YEAR(transaction_date) AS year,
        MONTH(transaction_date) AS month,
        SUM(amount) AS total_revenue
    FROM financial_transactions
    WHERE account_type = 'Revenue'
    GROUP BY YEAR(transaction_date), MONTH(transaction_date)
) x
GROUP BY year
ORDER BY year;


-- Year-over-Year Revenue Growth %
SELECT
    ROUND(
        (
            MAX(CASE WHEN year = 2023 THEN yearly_revenue END)
            -
            MAX(CASE WHEN year = 2022 THEN yearly_revenue END)
        )
        /
        MAX(CASE WHEN year = 2022 THEN yearly_revenue END)
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


-- Monthly Expense Trend
SELECT
    YEAR(transaction_date) AS year,
    MONTH(transaction_date) AS month,
    SUM(ABS(amount)) AS total_expense
FROM financial_transactions
WHERE account_type = 'Expense'
GROUP BY YEAR(transaction_date), MONTH(transaction_date)
ORDER BY year, month;


-- Monthly Profit
SELECT
    YEAR(transaction_date) AS year,
    MONTH(transaction_date) AS month,
    SUM(CASE
        WHEN account_type = 'Revenue' THEN amount
        WHEN account_type = 'Expense' THEN amount
        ELSE 0
    END) AS monthly_profit
FROM financial_transactions
GROUP BY YEAR(transaction_date), MONTH(transaction_date)
ORDER BY year, month;


-- Monthly Profit Margin
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
        SUM(CASE
            WHEN account_type = 'Revenue' THEN amount
            ELSE 0
        END)
        * 100,
        2
    ) AS profit_margin_pct
FROM financial_transactions
GROUP BY YEAR(transaction_date), MONTH(transaction_date)
ORDER BY year, month;


-- Highest Revenue Months
SELECT
    YEAR(transaction_date) AS year,
    MONTH(transaction_date) AS month,
    SUM(amount) AS total_revenue
FROM financial_transactions
WHERE account_type = 'Revenue'
GROUP BY YEAR(transaction_date), MONTH(transaction_date)
ORDER BY total_revenue DESC
LIMIT 5;


-- Lowest Revenue Months
SELECT
    YEAR(transaction_date) AS year,
    MONTH(transaction_date) AS month,
    SUM(amount) AS total_revenue
FROM financial_transactions
WHERE account_type = 'Revenue'
GROUP BY YEAR(transaction_date), MONTH(transaction_date)
ORDER BY total_revenue
LIMIT 5;