import os
import sys
import pytest
from sqlalchemy import create_engine, text

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.query_validator import query_validator
from app.services.metadata_extractor import metadata_extractor
from app.db.adapters import SQLiteAdapter

@pytest.fixture
def temp_db():
    """Fixture to set up a temporary SQLite database on disk."""
    db_file = "./test_temp.db"
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except Exception:
            pass
            
    db_url = f"sqlite:///{db_file}"
    engine = create_engine(db_url)
    
    # Create test tables
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE test_users (
                id INTEGER PRIMARY KEY,
                name VARCHAR(50) NOT NULL,
                email VARCHAR(50) UNIQUE
            );
        """))
        conn.execute(text("""
            CREATE TABLE test_orders (
                order_id INTEGER PRIMARY KEY,
                user_id INTEGER,
                amount DECIMAL(10,2),
                FOREIGN KEY (user_id) REFERENCES test_users(id)
            );
        """))
        conn.execute(text("INSERT INTO test_users VALUES (1, 'Alice', 'alice@test.com');"))
        conn.execute(text("INSERT INTO test_orders VALUES (10, 1, 99.50);"))
        
    yield db_url
    engine.dispose()
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except Exception:
            pass

def test_sql_validator_safe_queries():
    """Verify that safe SELECT queries pass validation."""
    query = "SELECT * FROM test_users WHERE name = 'Alice';"
    is_safe, msg = query_validator.validate_sql(query)
    assert is_safe is True
    assert "valid" in msg.lower()

def test_sql_validator_unsafe_queries():
    """Verify that destructive SQL operations are rejected."""
    unsafe_queries = [
        "DROP TABLE test_users;",
        "DELETE FROM test_users WHERE id = 1;",
        "UPDATE test_users SET name = 'Bob';",
        "INSERT INTO test_users VALUES (2, 'Bob', 'bob@test.com');",
        "ALTER TABLE test_users ADD COLUMN age INTEGER;",
        "SELECT * FROM test_users; DROP TABLE test_users;"
    ]
    
    for q in unsafe_queries:
        is_safe, msg = query_validator.validate_sql(q)
        assert is_safe is False
        assert "violation" in msg.lower()

def test_sql_validator_enforce_limit():
    """Verify that row limits are correctly enforced or appended."""
    # No limit
    q1 = "SELECT * FROM test_users"
    assert "LIMIT 1000" in query_validator.enforce_limit(q1, 1000)
    
    # Limit exceeds max
    q2 = "SELECT * FROM test_users LIMIT 5000;"
    assert "LIMIT 1000" in query_validator.enforce_limit(q2, 1000)
    
    # Valid limit remains unchanged
    q3 = "SELECT * FROM test_users LIMIT 50;"
    assert "LIMIT 50" in query_validator.enforce_limit(q3, 1000)

def test_database_adapter_reflection(temp_db):
    """Verify that the SQLite adapter can reflect schema metadata correctly."""
    adapter = SQLiteAdapter(temp_db)
    adapter.connect()
    
    schema = adapter.get_schema_metadata()
    assert len(schema) == 2
    
    tables = {t["name"]: t for t in schema}
    assert "test_users" in tables
    assert "test_orders" in tables
    
    # Check column reflection
    user_cols = {c["name"]: c for c in tables["test_users"]["columns"]}
    assert "name" in user_cols
    assert user_cols["id"]["is_primary"] is True
    
    # Check foreign key reflection
    order_cols = {c["name"]: c for c in tables["test_orders"]["columns"]}
    assert order_cols["user_id"]["is_foreign"] is True
    assert order_cols["user_id"]["foreign_key_table"] == "test_users"
    assert order_cols["user_id"]["foreign_key_column"] == "id"
    
    adapter.disconnect()

def test_metadata_extractor_formatting():
    """Verify schema text and prompt formatting."""
    mock_table = {
        "name": "employees",
        "description": "Store employee profiles",
        "columns": [
            {"name": "emp_id", "data_type": "INTEGER", "is_primary": True, "is_foreign": False},
            {"name": "salary", "data_type": "DECIMAL", "is_primary": False, "is_foreign": False, "description": "Base salary"}
        ]
    }
    
    embeddings_text = metadata_extractor.format_table_for_embeddings(mock_table)
    assert "Table Name: employees" in embeddings_text
    assert "Store employee profiles" in embeddings_text
    assert "Base salary" in embeddings_text
    
    prompt_ddl = metadata_extractor.format_schema_for_prompt([mock_table])
    assert "CREATE TABLE employees" in prompt_ddl
    assert "emp_id INTEGER PRIMARY KEY" in prompt_ddl
