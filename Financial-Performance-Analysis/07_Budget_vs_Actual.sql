USE financial_performance;


-- =========================================================
-- BUDGET VS ACTUAL ANALYSIS
-- =========================================================


-- 1. Budget by Business Unit
SELECT
    business_unit,
    SUM(budgeted_revenue) AS total_budgeted_revenue,
    SUM(budgeted_expense) AS total_budgeted_expense
FROM budget
GROUP BY business_unit
ORDER BY total_budgeted_revenue DESC;


-- 2. Actual Revenue & Expense by Business Unit
SELECT
    business_unit,
    SUM(CASE
        WHEN account_type = 'Revenue' THEN amount
        ELSE 0
    END) AS actual_revenue,
    SUM(CASE
        WHEN account_type = 'Expense' THEN ABS(amount)
        ELSE 0
    END) AS actual_expense
FROM financial_transactions
GROUP BY business_unit
ORDER BY actual_revenue DESC;


-- 3. Budget vs Actual by Business Unit
SELECT
    b.business_unit,
    b.total_budgeted_revenue,
    a.actual_revenue,
    a.actual_revenue - b.total_budgeted_revenue AS revenue_variance,

    b.total_budgeted_expense,
    a.actual_expense,
    a.actual_expense - b.total_budgeted_expense AS expense_variance

FROM
(
    SELECT
        business_unit,
        SUM(budgeted_revenue) AS total_budgeted_revenue,
        SUM(budgeted_expense) AS total_budgeted_expense
    FROM budget
    GROUP BY business_unit
) b

JOIN
(
    SELECT
        business_unit,

        SUM(CASE
            WHEN account_type = 'Revenue' THEN amount
            ELSE 0
        END) AS actual_revenue,

        SUM(CASE
            WHEN account_type = 'Expense' THEN ABS(amount)
            ELSE 0
        END) AS actual_expense

    FROM financial_transactions
    GROUP BY business_unit
) a

ON b.business_unit = a.business_unit

ORDER BY revenue_variance DESC;


-- 4. Revenue and Expense Variance %
SELECT
    b.business_unit,

    ROUND(
        (a.actual_revenue - b.total_budgeted_revenue)
        / NULLIF(b.total_budgeted_revenue, 0) * 100,
        2
    ) AS revenue_variance_pct,

    ROUND(
        (a.actual_expense - b.total_budgeted_expense)
        / NULLIF(b.total_budgeted_expense, 0) * 100,
        2
    ) AS expense_variance_pct

FROM
(
    SELECT
        business_unit,
        SUM(budgeted_revenue) AS total_budgeted_revenue,
        SUM(budgeted_expense) AS total_budgeted_expense
    FROM budget
    GROUP BY business_unit
) b

JOIN
(
    SELECT
        business_unit,

        SUM(CASE
            WHEN account_type = 'Revenue' THEN amount
            ELSE 0
        END) AS actual_revenue,

        SUM(CASE
            WHEN account_type = 'Expense' THEN ABS(amount)
            ELSE 0
        END) AS actual_expense

    FROM financial_transactions
    GROUP BY business_unit
) a

ON b.business_unit = a.business_unit

ORDER BY revenue_variance_pct DESC;


-- 5. Budgeted Profit vs Actual Profit
SELECT
    b.business_unit,

    b.total_budgeted_revenue - b.total_budgeted_expense
        AS budgeted_profit,

    a.actual_revenue - a.actual_expense
        AS actual_profit,

    (a.actual_revenue - a.actual_expense)
        -
    (b.total_budgeted_revenue - b.total_budgeted_expense)
        AS profit_variance

FROM
(
    SELECT
        business_unit,
        SUM(budgeted_revenue) AS total_budgeted_revenue,
        SUM(budgeted_expense) AS total_budgeted_expense
    FROM budget
    GROUP BY business_unit
) b

JOIN
(
    SELECT
        business_unit,

        SUM(CASE
            WHEN account_type = 'Revenue' THEN amount
            ELSE 0
        END) AS actual_revenue,

        SUM(CASE
            WHEN account_type = 'Expense' THEN ABS(amount)
            ELSE 0
        END) AS actual_expense

    FROM financial_transactions
    GROUP BY business_unit
) a

ON b.business_unit = a.business_unit

ORDER BY actual_profit DESC;


-- 6. Budget vs Actual by Month and Business Unit
SELECT
    b.year,
    b.month,
    b.business_unit,

    b.budgeted_revenue,

    COALESCE(a.actual_revenue, 0) AS actual_revenue,

    COALESCE(a.actual_revenue, 0)
        - b.budgeted_revenue AS revenue_variance,

    b.budgeted_expense,

    COALESCE(a.actual_expense, 0) AS actual_expense,

    COALESCE(a.actual_expense, 0)
        - b.budgeted_expense AS expense_variance

FROM budget b

LEFT JOIN
(
    SELECT
        YEAR(transaction_date) AS year,
        MONTH(transaction_date) AS month,
        business_unit,

        SUM(CASE
            WHEN account_type = 'Revenue' THEN amount
            ELSE 0
        END) AS actual_revenue,

        SUM(CASE
            WHEN account_type = 'Expense' THEN ABS(amount)
            ELSE 0
        END) AS actual_expense

    FROM financial_transactions

    GROUP BY
        YEAR(transaction_date),
        MONTH(transaction_date),
        business_unit

) a

ON b.year = a.year
AND b.month = a.month
AND b.business_unit = a.business_unit

ORDER BY
    b.year,
    b.month,
    b.business_unit;


-- 7. Budget vs Actual Profit by Month
SELECT
    b.year,
    b.month,
    b.business_unit,

    b.budgeted_revenue - b.budgeted_expense
        AS budgeted_profit,

    COALESCE(a.actual_revenue, 0)
        - COALESCE(a.actual_expense, 0)
        AS actual_profit,

    (
        COALESCE(a.actual_revenue, 0)
        - COALESCE(a.actual_expense, 0)
    )
    -
    (
        b.budgeted_revenue - b.budgeted_expense
    ) AS profit_variance

FROM budget b

LEFT JOIN
(
    SELECT
        YEAR(transaction_date) AS year,
        MONTH(transaction_date) AS month,
        business_unit,

        SUM(CASE
            WHEN account_type = 'Revenue' THEN amount
            ELSE 0
        END) AS actual_revenue,

        SUM(CASE
            WHEN account_type = 'Expense' THEN ABS(amount)
            ELSE 0
        END) AS actual_expense

    FROM financial_transactions

    GROUP BY
        YEAR(transaction_date),
        MONTH(transaction_date),
        business_unit

) a

ON b.year = a.year
AND b.month = a.month
AND b.business_unit = a.business_unit

ORDER BY
    b.year,
    b.month,
    b.business_unit;