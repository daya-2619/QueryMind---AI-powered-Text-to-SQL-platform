import os
import sys
import pytest

# Append parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.llm import llm_service
from app.core.config import settings

# Sample schema DDL for testing compiler
SCHEMA_DDL = """
CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    city VARCHAR(50) NOT NULL,
    country VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE products (
    product_id INTEGER PRIMARY KEY,
    product_name VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    stock_quantity INTEGER NOT NULL
);

CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER,
    order_date TIMESTAMP NOT NULL,
    total_amount DECIMAL(10, 2) NOT NULL,
    status VARCHAR(20) NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE order_items (
    order_item_id INTEGER PRIMARY KEY,
    order_id INTEGER,
    product_id INTEGER,
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);
"""

def test_local_compiler_simple_query():
    # Force local mode
    settings.LLM_PROVIDER = "local"
    
    question = "Show all customers from Kolkata"
    res = llm_service.generate_sql_response(question, SCHEMA_DDL)
    
    sql = res["sql"].lower()
    assert "select" in sql
    assert "from customers" in sql
    assert "city = 'kolkata'" in sql

def test_local_compiler_multi_table_join():
    settings.LLM_PROVIDER = "local"
    
    question = "Show product names purchased by customers in Mumbai"
    res = llm_service.generate_sql_response(question, SCHEMA_DDL)
    
    sql = res["sql"].lower()
    assert "join orders" in sql
    assert "join order_items" in sql
    assert "join products" in sql
    assert "city = 'mumbai'" in sql

def test_local_compiler_numeric_and_having_filter():
    settings.LLM_PROVIDER = "local"
    
    # regular WHERE numeric filter
    q1 = "products with price greater than 100"
    res1 = llm_service.generate_sql_response(q1, SCHEMA_DDL)
    assert "price > 100" in res1["sql"].lower()
    
    # HAVING filter on aggregates
    q2 = "customers who spent more than 500 dollars"
    res2 = llm_service.generate_sql_response(q2, SCHEMA_DDL)
    sql2 = res2["sql"].lower()
    assert "having sum(" in sql2
    assert "> 500" in sql2

def test_local_compiler_date_filters():
    settings.LLM_PROVIDER = "local"
    
    q1 = "orders in the last 30 days"
    res1 = llm_service.generate_sql_response(q1, SCHEMA_DDL)
    sql1 = res1["sql"].lower()
    assert "order_date >= datetime(" in sql1 or "order_date >= current_date" in sql1
    
    q2 = "orders in 2023"
    res2 = llm_service.generate_sql_response(q2, SCHEMA_DDL)
    sql2 = res2["sql"].lower()
    assert "strftime('%y'" in sql2 or "extract(year" in sql2

def test_local_compiler_conversational_history():
    settings.LLM_PROVIDER = "local"
    
    # History contains previous question and query
    chat_history = [
        {"role": "user", "content": "Show all orders"},
        {"role": "assistant", "content": "Generated SQL: SELECT orders.order_id, orders.total_amount, orders.status FROM orders LIMIT 1000."}
    ]
    
    # Follow-up query
    follow_up = "only those in Kolkata"
    res = llm_service.generate_sql_response(follow_up, SCHEMA_DDL, chat_history)
    
    sql = res["sql"].lower()
    # Should join customers and check city = 'Kolkata'
    assert "from orders" in sql
    assert "join customers" in sql
    assert "city = 'kolkata'" in sql
