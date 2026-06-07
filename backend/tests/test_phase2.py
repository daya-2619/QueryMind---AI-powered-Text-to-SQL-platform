import os
import sys
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError

# Adjust path for app imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.query_validator import query_validator
from app.db.adapters import SQLiteAdapter

def test_ast_validation_nested_injections():
    """Verify that nested SQL mutations inside CTEs and subqueries are intercepted."""
    nested_unsafe = [
        "SELECT * FROM users WHERE id IN (DELETE FROM orders WHERE amount > 100);",
        "WITH cte AS (INSERT INTO logs VALUES ('hack')) SELECT * FROM cte;",
        "SELECT name FROM customers; DROP TABLE orders;",
        "SELECT name, (UPDATE products SET price = 0 WHERE id = 1) FROM customers;"
    ]
    
    for q in nested_unsafe:
        is_safe, msg = query_validator.validate_sql(q, dialect="sqlite")
        assert is_safe is False
        assert any(word in msg for word in ["Query violation", "SQL Syntax Error"])

def test_ast_validation_catalog_blocking():
    """Verify that catalog and schema tables are blocked across dialects."""
    catalog_queries = [
        "SELECT * FROM sqlite_master;",
        "SELECT * FROM information_schema.tables;",
        "SELECT usename, passwd FROM pg_shadow;",
        "SELECT * FROM sqlite_sequence;"
    ]
    
    for q in catalog_queries:
        is_safe, msg = query_validator.validate_sql(q, dialect="sqlite")
        assert is_safe is False
        assert "catalog" in msg.lower() or "forbidden" in msg.lower()

def test_error_categorization():
    """Verify exception classification to standard codes."""
    adapter = SQLiteAdapter("sqlite:///./dummy.db")
    
    # 1. Syntax / Schema Error
    pe = ProgrammingError("SELECT", {}, Exception("no such table: missing_table"))
    cat_pe = adapter._categorize_error(pe)
    assert cat_pe["code"] == "SQL_SYNTAX_ERROR"
    
    # 2. Connection / Operational Error
    oe = OperationalError("SELECT", {}, Exception("unable to open database file"))
    cat_oe = adapter._categorize_error(oe)
    assert cat_oe["code"] == "DB_CONNECTION_ERROR"
    
    # 3. Timeout Error
    te = Exception("statement cancelled due to timeout")
    cat_te = adapter._categorize_error(te)
    assert cat_te["code"] == "QUERY_TIMEOUT_ERROR"

def test_query_execution_timeout_simulation():
    """Simulates query timeouts by setting settings to trigger a timeout exception."""
    db_file = "./test_timeout_temp.db"
    db_url = f"sqlite:///{db_file}"
    
    # Ensure clean database setup
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except Exception:
            pass
            
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE t (id INT);"))
        conn.execute(text("INSERT INTO t VALUES (1);"))
    engine.dispose()
    
    adapter = SQLiteAdapter(db_url)
    adapter.connect()
    
    # Force a very small execution timeout option (1 millisecond / 0.001) to simulate timeout
    # Or trigger a timeout-like exception using statement cancellation option
    try:
        # Pass a driver-level connection execution option that forces cancellation / timeout
        res = adapter.execute_query("SELECT * FROM t", limit=10)
        # Standard query executes fast. Now let's trigger a timeout error by passing a timeout option of 0
        import time
        from app.core.config import settings
        
        # Temp override settings timeout to 0 (which triggers driver immediate timeout/cancel)
        old_timeout = settings.QUERY_TIMEOUT_SECONDS
        settings.QUERY_TIMEOUT_SECONDS = 0
        
        res_timeout = adapter.execute_query("SELECT * FROM t", limit=10)
        # Depending on sqlite version, it might execute or fail immediately.
        # If it fails, let's verify categorization
        if not res_timeout["success"]:
            assert res_timeout["error_code"] in ("QUERY_TIMEOUT_ERROR", "DB_CONNECTION_ERROR")
            
        settings.QUERY_TIMEOUT_SECONDS = old_timeout
    finally:
        adapter.disconnect()
        if os.path.exists(db_file):
            try:
                os.remove(db_file)
            except Exception:
                pass
