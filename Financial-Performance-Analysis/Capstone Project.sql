CREATE DATABASE financial_performance;
USE financial_performance;


-- Create Table Customers
CREATE TABLE customers (
    customer_id VARCHAR(50) NOT NULL,
    customer_name VARCHAR(255),
    segment VARCHAR(100),
    join_date DATE,
    region VARCHAR(100),
    PRIMARY KEY (customer_id)
);
DESCRIBE customers;

-- Create Table Vendors
CREATE TABLE vendors (
    vendor_id VARCHAR(50) NOT NULL,
    vendor_name VARCHAR(255),
    category VARCHAR(100),
    region VARCHAR(100),
    active VARCHAR(20),
    PRIMARY KEY (vendor_id)
);
DESCRIBE vendors;

 -- Create Table Headcount
 CREATE TABLE headcount (
    employee_id VARCHAR(50) NOT NULL,
    employee_name VARCHAR(255),
    business_unit VARCHAR(100),
    join_date DATE,
    status VARCHAR(20),
    region VARCHAR(100),
    cost_to_company INT,
    PRIMARY KEY (employee_id)
);
DESCRIBE headcount;

-- Create Table Budget
CREATE TABLE budget (
    year INT NOT NULL,
    month INT NOT NULL,
    business_unit VARCHAR(100) NOT NULL,
    budgeted_revenue INT,
    budgeted_expense INT,
    PRIMARY KEY (year, month, business_unit),
    CHECK (month BETWEEN 1 AND 12)
);
DESCRIBE Budget;

-- Create Table Financial_Tarnsactions
CREATE TABLE financial_transactions (
    transaction_id VARCHAR(50) NOT NULL,
    transaction_date DATE NOT NULL,
    amount DECIMAL(15,2) NOT NULL,
    account_type VARCHAR(50) NOT NULL,
    category VARCHAR(100) NOT NULL,
    business_unit VARCHAR(100) NOT NULL,
    region VARCHAR(100) NOT NULL,
    customer_id VARCHAR(50),
    vendor_id VARCHAR(50),
    description VARCHAR(500),

    PRIMARY KEY (transaction_id),

    FOREIGN KEY (customer_id)
        REFERENCES customers(customer_id),

    FOREIGN KEY (vendor_id)
        REFERENCES vendors(vendor_id)
);
DESCRIBE financial_transactions;

ALTER TABLE customers
ADD COLUMN status VARCHAR(20) AFTER region;

SELECT COUNT(*) AS customer_count
FROM customers;

SELECT *
FROM customers
LIMIT 5;

SELECT COUNT(*) AS vendor_count
FROM vendors;

SELECT *
FROM vendors
LIMIT 5;

SELECT COUNT(*) AS headcount_count
FROM headcount;

SELECT *
FROM headcount
LIMIT 5;


SELECT COUNT(*) AS budget_count
FROM budget;

SELECT *
FROM budget
LIMIT 5;

SHOW TABLES;
DESCRIBE financial_transactions;
SELECT @@FOREIGN_KEY_CHECKS AS foreign_key_checks;
SHOW WARNINGS;
SHOW CREATE TABLE financial_transactions;
SHOW ENGINE INNODB STATUS;

CREATE TABLE financial_transactions_staging (
    transaction_id VARCHAR(50),
    transaction_date VARCHAR(50),
    amount VARCHAR(50),
    account_type VARCHAR(50),
    category VARCHAR(100),
    business_unit VARCHAR(100),
    region VARCHAR(100),
    customer_id VARCHAR(50),
    vendor_id VARCHAR(50),
    description VARCHAR(500)
);

SELECT COUNT(*) AS staging_count
FROM financial_transactions_staging;

SELECT *
FROM financial_transactions_staging
LIMIT 5;

INSERT INTO financial_transactions (
    transaction_id,
    transaction_date,
    amount,
    account_type,
    category,
    business_unit,
    region,
    customer_id,
    vendor_id,
    description
)
SELECT
    transaction_id,
    STR_TO_DATE(transaction_date, '%d-%m-%Y'),
    CAST(REPLACE(amount, ',', '') AS DECIMAL(15,2)),
    account_type,
    category,
    business_unit,
    region,
    NULLIF(TRIM(customer_id), ''),
    NULLIF(TRIM(vendor_id), ''),
    description
FROM financial_transactions_staging;

SELECT COUNT(*) AS transaction_count
FROM financial_transactions;

SELECT *
FROM financial_transactions
LIMIT 5;

SELECT COUNT(*) AS invalid_customer_ids
FROM financial_transactions ft
LEFT JOIN customers c
    ON ft.customer_id = c.customer_id
WHERE ft.customer_id IS NOT NULL
  AND c.customer_id IS NULL;
  
  SELECT COUNT(*) AS invalid_vendor_ids
FROM financial_transactions ft
LEFT JOIN vendors v
    ON ft.vendor_id = v.vendor_id
WHERE ft.vendor_id IS NOT NULL
  AND v.vendor_id IS NULL;
  
  SELECT
    COUNT(*) AS total_transactions,
    COUNT(DISTINCT transaction_id) AS unique_transaction_ids
FROM financial_transactions;


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

-- Check transaction amount integrity
SELECT
    COUNT(*) AS total_transactions,
    SUM(amount > 0) AS positive_amounts,
    SUM(amount < 0) AS negative_amounts,
    SUM(amount = 0) AS zero_amounts
FROM financial_transactions;

-- Validate transaction date range
SELECT
    MIN(transaction_date) AS earliest_transaction,
    MAX(transaction_date) AS latest_transaction
FROM financial_transactions;


-- Check transaction categories
SELECT
    account_type,
    COUNT(*) AS transaction_count,
    SUM(amount) AS total_amount
FROM financial_transactions
GROUP BY account_type
ORDER BY account_type;


-- Check Revenue/Expense sign consistency
SELECT
    SUM(account_type = 'Revenue' AND amount <= 0) AS invalid_revenue,
    SUM(account_type = 'Expense' AND amount >= 0) AS invalid_expense
FROM financial_transactions;


-- Check business-unit consistency
SELECT
    business_unit,
    COUNT(*) AS transaction_count,
    SUM(amount) AS total_amount
FROM financial_transactions
GROUP BY business_unit
ORDER BY business_unit;

-- Region distribution
SELECT
    region,
    COUNT(*) AS transaction_count,
    SUM(amount) AS total_amount
FROM financial_transactions
GROUP BY region
ORDER BY region;

-- Category validation
SELECT
    category,
    COUNT(*) AS transaction_count,
    SUM(amount) AS total_amount
FROM financial_transactions
GROUP BY category
ORDER BY category;

-- Customer/Vendor assignment logic
SELECT
    SUM(account_type = 'Revenue' AND customer_id IS NULL) AS revenue_without_customer,
    SUM(account_type = 'Expense' AND vendor_id IS NULL) AS expense_without_vendor,
    SUM(account_type = 'Revenue' AND vendor_id IS NOT NULL) AS revenue_with_vendor,
    SUM(account_type = 'Expense' AND customer_id IS NOT NULL) AS expense_with_customer
FROM financial_transactions;

-- Check duplicate transaction records
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

-- Calculate YoY Growth
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
        WHEN account_type IN ('Revenue' , 'Expense') THEN amount
        ELSE 0
    END) AS net_result
FROM
    financial_transactions
GROUP BY YEAR(transaction_date) , MONTH(transaction_date)
ORDER BY year , month;
    
    -- Best Performing Month
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

-- Category-wise Performance
SELECT
    category,
    COUNT(*) AS transaction_count,
    SUM(amount) AS total_amount
FROM financial_transactions
GROUP BY category
ORDER BY total_amount DESC;

-- Revenue Categories
SELECT
    category,
    COUNT(*) AS transaction_count,
    SUM(amount) AS revenue
FROM financial_transactions
WHERE account_type = 'Revenue'
GROUP BY category
ORDER BY revenue DESC;

-- Expense Categories
SELECT
    category,
    COUNT(*) AS transaction_count,
    SUM(amount) AS expense
FROM financial_transactions
WHERE account_type = 'Expense'
GROUP BY category
ORDER BY expense ASC;

-- Expense Category Share
SELECT
    category,
    ROUND(ABS(SUM(amount)), 2) AS expense,
    ROUND(
        ABS(SUM(amount))
        /
        (SELECT ABS(SUM(amount))
         FROM financial_transactions
         WHERE account_type = 'Expense')
        * 100,
        2
    ) AS expense_share_percent
FROM financial_transactions
WHERE account_type = 'Expense'
GROUP BY category
ORDER BY expense_share_percent DESC;

-- Revenue Category Share
SELECT
    category,
    ROUND(SUM(amount), 2) AS revenue,
    ROUND(
        SUM(amount)
        /
        (SELECT SUM(amount)
         FROM financial_transactions
         WHERE account_type = 'Revenue')
        * 100,
        2
    ) AS revenue_share_percent
FROM financial_transactions
WHERE account_type = 'Revenue'
GROUP BY category
ORDER BY revenue_share_percent DESC;

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
    
    -- Yearly Revenue Growth
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
    
    -- Revenue by Region
    SELECT
    region,
    COUNT(*) AS revenue_transactions,
    SUM(amount) AS total_revenue
FROM financial_transactions
WHERE account_type = 'Revenue'
GROUP BY region
ORDER BY total_revenue DESC;

-- Revenue Category by Region
SELECT
    region,
    category,
    SUM(amount) AS revenue
FROM financial_transactions
WHERE account_type = 'Revenue'
GROUP BY
    region,
    category
ORDER BY
    region,
    revenue DESC;
    
    -- Customer Revenue Analysis
    SELECT
    customer_id,
    COUNT(*) AS transaction_count,
    SUM(amount) AS total_revenue
FROM financial_transactions
WHERE account_type = 'Revenue'
GROUP BY customer_id
ORDER BY total_revenue DESC
LIMIT 10;


-- Top Customers with Details
SELECT
    c.customer_id,
    c.customer_name,
    c.segment,
    c.region,
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

-- Revenue by Customer Segment
SELECT
    c.segment,
    COUNT(DISTINCT c.customer_id) AS customers,
    SUM(ft.amount) AS total_revenue
FROM financial_transactions ft
JOIN customers c
    ON ft.customer_id = c.customer_id
WHERE ft.account_type = 'Revenue'
GROUP BY c.segment
ORDER BY total_revenue DESC;

-- Average Revenue per Customer Segment
SELECT
    c.segment,
    COUNT(DISTINCT c.customer_id) AS customers,
    ROUND(
        SUM(ft.amount) / COUNT(DISTINCT c.customer_id),
        2
    ) AS avg_revenue_per_customer
FROM financial_transactions ft
JOIN customers c
    ON ft.customer_id = c.customer_id
WHERE ft.account_type = 'Revenue'
GROUP BY c.segment
ORDER BY avg_revenue_per_customer DESC;

-- Vendor Expense Analysis
SELECT
    vendor_id,
    COUNT(*) AS expense_transactions,
    SUM(ABS(amount)) AS total_expense
FROM financial_transactions
WHERE account_type = 'Expense'
GROUP BY vendor_id
ORDER BY total_expense DESC
LIMIT 10;

-- Top Vendors with Vendor Details
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

-- Expense by Vendor Category
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

-- Vendor Expense by Region
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

-- Vendor Average Expense
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

-- Budget vs Actual
SELECT
    year,
    month,
    business_unit,
    budgeted_revenue,
    budgeted_expense
FROM budget
ORDER BY
    year,
    month,
    business_unit;
    
    -- Total Budget by Business Unit
    SELECT
    business_unit,
    SUM(budgeted_revenue) AS total_budgeted_revenue,
    SUM(budgeted_expense) AS total_budgeted_expense
FROM budget
GROUP BY business_unit
ORDER BY total_budgeted_revenue DESC;

-- Actual Revenue & Expense by Business Unit
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

-- Budget vs Actual
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

-- Revenue Variance %
SELECT
    b.business_unit,

    ROUND(
        (a.actual_revenue - b.total_budgeted_revenue)
        / b.total_budgeted_revenue * 100,
        2
    ) AS revenue_variance_pct,

    ROUND(
        (a.actual_expense - b.total_budgeted_expense)
        / b.total_budgeted_expense * 100,
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


 -- Budgeted Profit vs Actual Profit
SELECT
    b.business_unit,

    b.total_budgeted_revenue - b.total_budgeted_expense
        AS budgeted_profit,

    a.actual_revenue - a.actual_expense
        AS actual_profit,

    (a.actual_revenue - a.actual_expense)
        - (b.total_budgeted_revenue - b.total_budgeted_expense)
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

-- Actual Profit Margin by Business Unit
SELECT
    business_unit,

    ROUND(
        (
            actual_revenue - actual_expense
        ) / actual_revenue * 100,
        2
    ) AS profit_margin_pct

FROM
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

ORDER BY profit_margin_pct DESC;

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

-- Profit by Expense Category
SELECT
    category,
    SUM(
        CASE
            WHEN account_type = 'Revenue' THEN amount
            WHEN account_type = 'Expense' THEN amount
            ELSE 0
        END
    ) AS net_amount
FROM financial_transactions
GROUP BY category
ORDER BY net_amount DESC;

-- Top Revenue Categories
SELECT
    category,
    COUNT(*) AS revenue_transactions,
    SUM(amount) AS total_revenue
FROM financial_transactions
WHERE account_type = 'Revenue'
GROUP BY category
ORDER BY total_revenue DESC
LIMIT 5;

-- Top Expense Categories
SELECT
    category,
    COUNT(*) AS expense_transactions,
    SUM(ABS(amount)) AS total_expense
FROM financial_transactions
WHERE account_type = 'Expense'
GROUP BY category
ORDER BY total_expense DESC
LIMIT 5;

-- Expense Category Contribution %
SELECT
    category,
    ROUND(
        SUM(ABS(amount))
        /
        (
            SELECT SUM(ABS(amount))
            FROM financial_transactions
            WHERE account_type = 'Expense'
        )
        * 100,
        2
    ) AS expense_percentage
FROM financial_transactions
WHERE account_type = 'Expense'
GROUP BY category
ORDER BY expense_percentage DESC;

-- Revenue Category Contribution %
SELECT
    category,
    ROUND(
        SUM(amount)
        /
        (
            SELECT SUM(amount)
            FROM financial_transactions
            WHERE account_type = 'Revenue'
        )
        * 100,
        2
    ) AS revenue_percentage
FROM financial_transactions
WHERE account_type = 'Revenue'
GROUP BY category
ORDER BY revenue_percentage DESC;

-- Monthly Revenue Trend
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
    
    -- Year-over-Year Revenue Growth
    -- How much did revenue grow from 2022 to 2023?
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
-- Question: How did expenses change month by month?
SELECT
    YEAR(transaction_date) AS year,
    MONTH(transaction_date) AS month,
    SUM(ABS(amount)) AS total_expense
FROM financial_transactions
WHERE account_type = 'Expense'
GROUP BY YEAR(transaction_date), MONTH(transaction_date)
ORDER BY year, month;

-- Monthly Profit
-- Question: What was the profit generated each month?
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

-- Highest Revenue Month
SELECT
    YEAR(transaction_date) AS year,
    MONTH(transaction_date) AS month,
    SUM(amount) AS total_revenue
FROM financial_transactions
WHERE account_type = 'Revenue'
GROUP BY YEAR(transaction_date), MONTH(transaction_date)
ORDER BY total_revenue DESC
LIMIT 5;

-- Lowest Revenue Month
SELECT
    YEAR(transaction_date) AS year,
    MONTH(transaction_date) AS month,
    SUM(amount) AS total_revenue
FROM financial_transactions
WHERE account_type = 'Revenue'
GROUP BY YEAR(transaction_date), MONTH(transaction_date)
ORDER BY total_revenue
LIMIT 5;

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

-- Top 10 Customers by Revenue
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

-- Customer Revenue Concentration
-- Question: What percentage of total revenue comes from the top 10 customers?
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

-- Top 10 Vendors by Expense
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

-- Vendor Expense Concentration
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

-- Monthly Budget vs Actual Revenue
SELECT
    b.year,
    b.month,
    b.business_unit,
    b.budgeted_revenue,
    COALESCE(a.actual_revenue, 0) AS actual_revenue,
    COALESCE(a.actual_revenue, 0) - b.budgeted_revenue AS revenue_variance

FROM budget b

LEFT JOIN
(
    SELECT
        YEAR(transaction_date) AS year,
        MONTH(transaction_date) AS month,
        business_unit,
        SUM(amount) AS actual_revenue
    FROM financial_transactions
    WHERE account_type = 'Revenue'
    GROUP BY YEAR(transaction_date), MONTH(transaction_date), business_unit
) a

ON b.year = a.year
AND b.month = a.month
AND b.business_unit = a.business_unit

ORDER BY b.year, b.month, b.business_unit;

-- Monthly Budget vs Actual Expense
SELECT
    b.year,
    b.month,
    b.business_unit,
    b.budgeted_expense,
    COALESCE(a.actual_expense, 0) AS actual_expense,
    COALESCE(a.actual_expense, 0) - b.budgeted_expense AS expense_variance

FROM budget b

LEFT JOIN
(
    SELECT
        YEAR(transaction_date) AS year,
        MONTH(transaction_date) AS month,
        business_unit,
        SUM(ABS(amount)) AS actual_expense
    FROM financial_transactions
    WHERE account_type = 'Expense'
    GROUP BY YEAR(transaction_date), MONTH(transaction_date), business_unit
) a

ON b.year = a.year
AND b.month = a.month
AND b.business_unit = a.business_unit

ORDER BY b.year, b.month, b.business_unit;

-- Budget vs Actual Profit by Month
SELECT
    b.year,
    b.month,
    b.business_unit,

    b.budgeted_revenue - b.budgeted_expense AS budgeted_profit,

    COALESCE(a.actual_revenue, 0)
    - COALESCE(a.actual_expense, 0) AS actual_profit,

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

    GROUP BY YEAR(transaction_date), MONTH(transaction_date), business_unit
) a

ON b.year = a.year
AND b.month = a.month
AND b.business_unit = a.business_unit

ORDER BY b.year, b.month, b.business_unit;

-- Total Revenue vs Total Expense
SELECT
    SUM(CASE
        WHEN account_type = 'Revenue' THEN amount
        ELSE 0
    END) AS total_revenue,

    SUM(CASE
        WHEN account_type = 'Expense' THEN ABS(amount)
        ELSE 0
    END) AS total_expense,

    SUM(CASE
        WHEN account_type = 'Revenue' THEN amount
        WHEN account_type = 'Expense' THEN amount
        ELSE 0
    END) AS total_profit
FROM financial_transactions;

-- Overall Profit Margin
SELECT
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
    ) AS overall_profit_margin_pct
FROM financial_transactions;

-- Final Data Validation
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