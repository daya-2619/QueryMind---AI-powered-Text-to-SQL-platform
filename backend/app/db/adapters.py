import time
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from app.core.config import settings

logger = logging.getLogger(__name__)

class BaseDatabaseAdapter(ABC):
    """Abstract Base Class for target databases."""
    
    def __init__(self, connection_url: str):
        self.connection_url = connection_url
        self.engine = None

    @abstractmethod
    def connect(self) -> None:
        """Establish database connection pool."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close database connection pool."""
        pass

    @abstractmethod
    def execute_query(
        self, 
        sql: str, 
        params: Optional[Dict[str, Any]] = None, 
        limit: int = settings.MAX_ROWS_LIMIT
    ) -> Dict[str, Any]:
        """Execute a SQL query safely and return columns and rows."""
        pass

    @abstractmethod
    def get_schema_metadata(self) -> List[Dict[str, Any]]:
        """Reflect database schema and extract metadata."""
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """Ping database to ensure connection is healthy."""
        pass


class SQLAlchemyDatabaseAdapter(BaseDatabaseAdapter):
    """Database adapter implemented using SQLAlchemy for multi-db support."""

    @property
    def dialect_name(self) -> str:
        if self.engine:
            return self.engine.dialect.name
        return "sqlite" if self.connection_url.startswith("sqlite") else "postgres"

    def connect(self) -> None:
        if not self.engine:
            # Configure pooling, timeouts, and ping options
            connect_args = {}
            if self.connection_url.startswith("sqlite"):
                connect_args = {"check_same_thread": False}
            else:
                connect_args = {
                    "connect_timeout": settings.QUERY_TIMEOUT_SECONDS
                }

            engine_kwargs = {
                "connect_args": connect_args,
                "pool_pre_ping": True
            }
            if not self.connection_url.startswith("sqlite"):
                engine_kwargs["pool_size"] = 5
                engine_kwargs["max_overflow"] = 10

            self.engine = create_engine(self.connection_url, **engine_kwargs)

    def disconnect(self) -> None:
        if self.engine:
            self.engine.dispose()
            self.engine = None

    def test_connection(self) -> bool:
        self.connect()
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False

    def _categorize_error(self, error: Exception) -> Dict[str, str]:
        """Maps target database exceptions to standard structured error categories."""
        from sqlalchemy.exc import OperationalError, ProgrammingError
        
        err_msg = str(error).lower()
        
        if "timeout" in err_msg or "timed out" in err_msg or "canceling statement" in err_msg:
            return {
                "code": "QUERY_TIMEOUT_ERROR",
                "message": "The query execution timed out. The database took too long to return results."
            }
        elif isinstance(error, OperationalError) or "connection" in err_msg or "cantconnect" in err_msg or "could not connect" in err_msg or "is not running" in err_msg or "unable to open database file" in err_msg:
            return {
                "code": "DB_CONNECTION_ERROR",
                "message": "Could not connect to the database. Verify connection settings, server status, and credentials."
            }
        elif isinstance(error, ProgrammingError) or "no such table" in err_msg or "does not exist" in err_msg or "no such column" in err_msg or "syntax error" in err_msg or "undefined_column" in err_msg or "undefined_table" in err_msg:
            return {
                "code": "SQL_SYNTAX_ERROR",
                "message": f"SQL syntax or schema error: The generated query references elements that do not exist or has formatting errors. details: {str(error)}"
            }
        elif "permission" in err_msg or "denied" in err_msg or "privilege" in err_msg:
            return {
                "code": "PERMISSION_DENIED",
                "message": "Access denied. You do not have the required permissions to perform this query on the database."
            }
        else:
            return {
                "code": "UNKNOWN_DATABASE_ERROR",
                "message": f"An unexpected database error occurred: {str(error)}"
            }

    def execute_query(
        self, 
        sql: str, 
        params: Optional[Dict[str, Any]] = None, 
        limit: int = settings.MAX_ROWS_LIMIT
    ) -> Dict[str, Any]:
        self.connect()
        params = params or {}
        
        start_time = time.time()
        retries = 3
        backoff_factor = 0.5
        
        last_exception = None
        for attempt in range(retries):
            try:
                with self.engine.connect() as conn:
                    # Enforce timeout using dialect options or execution timeout settings
                    conn_exec = conn.execution_options(timeout=settings.QUERY_TIMEOUT_SECONDS)
                    result = conn_exec.execute(text(sql), params)
                    
                    columns = list(result.keys())
                    rows = []
                    for i, row in enumerate(result):
                        if i >= limit:
                            logger.warning(f"Query result truncated to limit of {limit} rows.")
                            break
                        row_dict = {}
                        for col_idx, col_name in enumerate(columns):
                            val = row[col_idx]
                            if isinstance(val, bytes):
                                val = val.hex()
                            row_dict[col_name] = val
                        rows.append(row_dict)
                    
                    execution_time_ms = (time.time() - start_time) * 1000
                    return {
                        "columns": columns,
                        "rows": rows,
                        "row_count": len(rows),
                        "execution_time_ms": execution_time_ms,
                        "success": True,
                        "error": None,
                        "error_code": None
                    }
            except Exception as e:
                last_exception = e
                # Check error categories; skip retry for syntax or permissions errors
                err_category = self._categorize_error(e)
                if err_category["code"] in ("SQL_SYNTAX_ERROR", "PERMISSION_DENIED"):
                    break
                
                logger.warning(f"Database query attempt {attempt + 1} failed: {e}. Retrying...")
                if attempt < retries - 1:
                    time.sleep(backoff_factor * (2 ** attempt))

        # Reaching here means all execution retries failed
        execution_time_ms = (time.time() - start_time) * 1000
        err_category = self._categorize_error(last_exception)
        logger.error(f"SQL execution failed: {last_exception}")
        
        return {
            "columns": [],
            "rows": [],
            "row_count": 0,
            "execution_time_ms": execution_time_ms,
            "success": False,
            "error": err_category["message"],
            "error_code": err_category["code"]
        }

    def get_schema_metadata(self) -> List[Dict[str, Any]]:
        """Reflect database metadata dynamically."""
        self.connect()
        inspector = inspect(self.engine)
        
        tables_metadata = []
        try:
            table_names = inspector.get_table_names()
            for table_name in table_names:
                columns = inspector.get_columns(table_name)
                pk_constraint = inspector.get_pk_constraint(table_name)
                pk_columns = pk_constraint.get("constrained_columns", []) if pk_constraint else []
                foreign_keys = inspector.get_foreign_keys(table_name)
                
                columns_meta = []
                for col in columns:
                    name = col["name"]
                    data_type = str(col["type"])
                    nullable = col.get("nullable", True)
                    is_pk = name in pk_columns
                    
                    # Find if this column is a foreign key
                    is_fk = False
                    fk_ref_table = None
                    fk_ref_column = None
                    for fk in foreign_keys:
                        if name in fk["constrained_columns"]:
                            is_fk = True
                            idx = fk["constrained_columns"].index(name)
                            fk_ref_table = fk["referred_table"]
                            fk_ref_column = fk["referred_columns"][idx]
                            break
                            
                    columns_meta.append({
                        "name": name,
                        "data_type": data_type,
                        "is_nullable": nullable,
                        "is_primary": is_pk,
                        "is_foreign": is_fk,
                        "foreign_key_table": fk_ref_table,
                        "foreign_key_column": fk_ref_column,
                        "description": col.get("comment", "") or f"Column {name} of type {data_type}"
                    })
                
                # Fetch actual row count
                row_count = 0
                try:
                    with self.engine.connect() as conn:
                        res = conn.execute(text(f"SELECT COUNT(*) FROM \"{table_name}\""))
                        row_count = res.scalar() or 0
                except Exception:
                    pass

                # Fetch table comment if supported by dialect
                table_desc = f"Table {table_name}"
                try:
                    comment_dict = inspector.get_table_comment(table_name)
                    if comment_dict and comment_dict.get("text"):
                        table_desc = comment_dict["text"]
                except (NotImplementedError, Exception):
                    pass

                tables_metadata.append({
                    "name": table_name,
                    "description": table_desc,
                    "columns": columns_meta,
                    "estimated_row_count": row_count
                })
                
            return tables_metadata
        except Exception as e:
            logger.exception("Error extracting schema metadata")
            return []


class PostgreSQLAdapter(SQLAlchemyDatabaseAdapter):
    """Specific Postgres Adapter for advanced configurations if needed."""
    pass


class SQLiteAdapter(SQLAlchemyDatabaseAdapter):
    """Specific SQLite Adapter for testing/development."""
    pass


def get_adapter(connection_url: str) -> BaseDatabaseAdapter:
    """Factory function to get database adapter based on URI scheme."""
    if connection_url.startswith("postgresql"):
        return PostgreSQLAdapter(connection_url)
    elif connection_url.startswith("sqlite"):
        return SQLiteAdapter(connection_url)
    else:
        # Fallback to standard SQLAlchemy reflection
        return SQLAlchemyDatabaseAdapter(connection_url)
