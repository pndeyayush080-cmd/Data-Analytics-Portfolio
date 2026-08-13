CREATE DATABASE retail_store;
USE retail_store;

-- Create Customers Table

CREATE TABLE customers (
    customer_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    phone VARCHAR(15),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Create Products Table

CREATE TABLE products (
    product_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL,
    price DECIMAL(10,2) NOT NULL CHECK (price > 0),
    stock_quantity INT NOT NULL DEFAULT 0,
    added_on DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Create Orders Table

CREATE TABLE orders (
    order_id INT PRIMARY KEY AUTO_INCREMENT,
    customer_id INT,
    order_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'Pending',
    total_amount DECIMAL(10,2),

    FOREIGN KEY (customer_id)
    REFERENCES customers(customer_id)
);

-- Create Order Items Table

CREATE TABLE order_items (
    order_item_id INT PRIMARY KEY AUTO_INCREMENT,
    order_id INT,
    product_id INT,
    quantity INT NOT NULL CHECK (quantity > 0),
    item_price DECIMAL(10,2) NOT NULL,

    FOREIGN KEY (order_id)
    REFERENCES orders(order_id),

    FOREIGN KEY (product_id)
    REFERENCES products(product_id)
);

-- Create Payments Table

CREATE TABLE payments (
    payment_id INT PRIMARY KEY AUTO_INCREMENT,
    order_id INT,
    payment_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    amount_paid DECIMAL(10,2) NOT NULL CHECK (amount_paid > 0),
    method VARCHAR(20) NOT NULL,

    FOREIGN KEY (order_id)
    REFERENCES orders(order_id)
);

-- Create Product Reviews Table

CREATE TABLE product_reviews (
    review_id INT PRIMARY KEY AUTO_INCREMENT,
    product_id INT,
    customer_id INT,
    rating INT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    review_text TEXT,
    review_date DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (product_id)
    REFERENCES products(product_id),

    FOREIGN KEY (customer_id)
    REFERENCES customers(customer_id)
);

SHOW TABLES;

-- Check Structure of Every Table

DESC customers;
DESC products;
DESC orders;
DESC order_items;
DESC payments;
DESC product_reviews;

-- Verify Data

SELECT COUNT(*) AS Total_Customers
FROM customers;
SELECT COUNT(*) AS Total_Products
FROM products;
SELECT COUNT(*) AS Total_Orders
FROM orders;
SELECT COUNT(*) AS Total_Order_Items
FROM order_items;
SELECT COUNT(*) AS Total_Payments
FROM payments;
SELECT COUNT(*) AS Total_Product_Reviews
FROM product_reviews;

-- Preview the Data

-- Customers
SELECT *
FROM customers;
-- Products
SELECT *
FROM products;
-- Orders
SELECT *
FROM orders;
-- Order Items
SELECT *
FROM order_items;
-- Payments
SELECT *
FROM payments;
-- Product Reviews
SELECT *
FROM product_reviews;

# Q1. Retrieve customer names and emails for email marketing.
SELECT
    name,
    email
FROM customers;

#Q2. View complete product catalog with all available details.
SELECT *
FROM products;

#Q3. List all unique product categories.
SELECT DISTINCT category
FROM products;

#Q4. Show all products priced above ₹1000.
SELECT *
FROM products
WHERE price > 1000;

#Q5. Display products within a mid-range price bracket (₹2000–₹5000).
SELECT *
FROM products
WHERE price BETWEEN 2000 AND 5000;

#Q6. Fetch data for specific customer IDs (Example: 1, 5, 10).
SELECT *
FROM customers
WHERE customer_id IN (1, 5, 10);

#Q7. Identify customers whose names start with the letter 'A'.
SELECT *
FROM customers
WHERE name LIKE 'A%';

#Q8. List electronics products priced under ₹3000.
SELECT *
FROM products
WHERE category = 'Electronics'
AND price < 3000;

#Q9. Display product names and prices in descending order of price.
SELECT
    name,
    price
FROM products
ORDER BY price DESC;


#Q10. Display product names and prices, sorted by price and then by name.
SELECT 
    name, price
FROM
    products
ORDER BY price DESC , name ASC;

# Filtering and Formatting:

#Q1. Retrieve orders where customer information is missing (possibly due to data migration or deletion).

SELECT *
FROM orders
WHERE customer_id IS NULL;

#Q2. Display customer names and emails using column aliases for frontend readability.

SELECT
    name AS Customer_Name,
    email AS Email_Address
FROM customers;

#Q3. Calculate total value per item ordered by multiplying quantity and item price.

SELECT
    order_item_id,
    order_id,
    product_id,
    quantity,
    item_price,
    quantity * item_price AS Total_Value
FROM order_items;


#Q4. Combine customer name and phone number in a single column.

SELECT
    CONCAT(name, ' - ', phone) AS Customer_Details
FROM customers;

#Q5. Extract only the date part from order timestamps for date-wise reporting.

SELECT
    order_id,
    DATE(order_date) AS Order_Date
FROM orders;

#Q6. List products that do not have any stock left.

SELECT *
FROM products
WHERE stock_quantity = 0;

# Aggregations:

#Q1. Count the total number of orders placed.

SELECT COUNT(*) AS Total_Orders
FROM orders;

#Q2. Calculate the total revenue collected from all orders.

SELECT SUM(total_amount) AS Total_Revenue
FROM orders;

#Q3. Calculate the average order value.

SELECT AVG(total_amount) AS Average_Order_Value
FROM orders;

#Q4. Count the number of customers who have placed at least one order.

SELECT COUNT(DISTINCT customer_id) AS Active_Customers
FROM orders;

#Q5. Find the number of orders placed by each customer.

SELECT
    customer_id,
    COUNT(order_id) AS Total_Orders
FROM orders
GROUP BY customer_id;

#Q6. Find the total sales amount made by each customer.

SELECT
    customer_id,
    SUM(total_amount) AS Total_Sales
FROM orders
GROUP BY customer_id;

#Q7. List the number of products sold per category.

SELECT
    p.category,
    SUM(oi.quantity) AS Products_Sold
FROM products p
JOIN order_items oi
ON p.product_id = oi.product_id
GROUP BY p.category;


#Q8. Find the average item price per category.

SELECT
    category,
    AVG(price) AS Average_Price
FROM products
GROUP BY category;

#Q9. Show the number of orders placed per day.

SELECT
    DATE(order_date) AS Order_Date,
    COUNT(order_id) AS Total_Orders
FROM orders
GROUP BY DATE(order_date)
ORDER BY Order_Date;

#Q10. List total payments received per payment method.

SELECT
    method,
    SUM(amount_paid) AS Total_Payment
FROM payments
GROUP BY method;

# JOINS 

#Q1. Display customer names along with their order details.

SELECT
    c.customer_id,
    c.name,
    o.order_id,
    o.order_date,
    o.status,
    o.total_amount
FROM customers c
INNER JOIN orders o
ON c.customer_id = o.customer_id;

# Q2. Get list of products that have been sold.

SELECT
    p.product_id,
    p.name,
    p.category,
    oi.quantity,
    oi.item_price
FROM products p
INNER JOIN order_items oi
ON p.product_id = oi.product_id;


# Q3. List all orders with their payment method.

SELECT
    o.order_id,
    o.order_date,
    o.status,
    o.total_amount,
    p.method,
    p.amount_paid
FROM orders o
INNER JOIN payments p
ON o.order_id = p.order_id;


# Q4. Get list of customers and their orders (LEFT JOIN)

SELECT
    c.customer_id,
    c.name,
    o.order_id,
    o.order_date,
    o.status,
    o.total_amount
FROM customers c
LEFT JOIN orders o
ON c.customer_id = o.customer_id;


# Q5. List all products along with order item quantity (LEFT JOIN)

SELECT
    p.product_id,
    p.name,
    p.category,
    oi.quantity
FROM products p
LEFT JOIN order_items oi
ON p.product_id = oi.product_id;


# Q6. List all payments including those with no matching orders (RIGHT JOIN)

SELECT
    o.order_id,
    o.order_date,
    p.payment_id,
    p.payment_date,
    p.amount_paid,
    p.method
FROM orders o
RIGHT JOIN payments p
ON o.order_id = p.order_id;


# Q7. Combine data from three tables: customer, order, and payment

SELECT
    c.customer_id,
    c.name,
    o.order_id,
    o.order_date,
    o.status,
    o.total_amount,
    p.payment_date,
    p.amount_paid,
    p.method
FROM customers c
INNER JOIN orders o
ON c.customer_id = o.customer_id
INNER JOIN payments p
ON o.order_id = p.order_id;


# LEVEL 6 : SET OPERATIONS

# Q1. List all customers who have either placed an order or written a product review.

SELECT customer_id
FROM orders

UNION

SELECT customer_id
FROM product_reviews;


# Q2. List all customers who have placed an order as well as reviewed a product.

SELECT
    customer_id,
    name
FROM customers
WHERE customer_id IN
(
    SELECT customer_id
    FROM orders
)
AND customer_id IN
(
    SELECT customer_id
    FROM product_reviews
);