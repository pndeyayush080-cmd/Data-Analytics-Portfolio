1. Core Financial KPIs

-- Core Financial KPIs
SELECT
    COUNT(*) AS total_transactions,
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
FROM financial_transactions;

2. Overall Net Margin

-- Net Margin
SELECT
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
FROM financial_transactions;