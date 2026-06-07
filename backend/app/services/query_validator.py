import logging
from typing import Tuple
import sqlglot
from sqlglot import exp
from app.core.config import settings

logger = logging.getLogger(__name__)

class QueryValidatorService:
    """Service to validate and sanitize generated SQL statements before execution using AST parsing."""

    # Explicit list of sqlglot nodes representing state mutations or dangerous instructions
    FORBIDDEN_NODE_TYPES = (
        exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter, 
        exp.Create, exp.TruncateTable, exp.Merge, exp.Command, exp.Transaction,
        exp.Schema, exp.Pragma, exp.Show
    )

    def validate_sql(self, sql: str, dialect: str = "sqlite") -> Tuple[bool, str]:
        """
        Validates whether a generated SQL query is safe to execute by parsing it into an AST.
        Args:
            sql: The raw SQL string.
            dialect: The target SQL dialect (e.g. 'sqlite', 'postgres').
        Returns:
            Tuple[bool, message]: (Is safe, details/error/warning message)
        """
        if not sql or not sql.strip():
            return False, "SQL query is empty."

        try:
            # Normalize common dialect mappings
            sqlglot_dialect = self._normalize_dialect(dialect)
            
            # Parse query; reject multiple statements (query chaining)
            expressions = sqlglot.parse(sql, read=sqlglot_dialect)
            if len(expressions) > 1:
                return False, "Query violation: Multiple SQL statements are not allowed."
            if not expressions or not expressions[0]:
                return False, "Query violation: Failed to parse SQL statement."
                
            expression = expressions[0]
            
            # 1. Root expression MUST be a SELECT or UNION
            # (which compiles to exp.Select or exp.Union)
            if not isinstance(expression, (exp.Select, exp.Union)):
                return False, f"Query violation: Only SELECT queries are allowed. Root node is '{expression.__class__.__name__}'."

            # 2. Walk AST to detect mutations, administrative queries, or PRAGMAs
            for node in expression.walk():
                if isinstance(node, self.FORBIDDEN_NODE_TYPES):
                    return False, f"Query violation: Dangerous SQL operation '{node.__class__.__name__}' is forbidden."
                
                # 3. Prevent system catalog database table reads
                if isinstance(node, exp.Table):
                    table_name = node.name.lower()
                    db_name = node.text("db").lower()
                    catalog_name = node.text("catalog").lower()
                    schema_name = node.text("schema").lower()
                    
                    for name in (table_name, db_name, catalog_name, schema_name):
                        if (
                            name.startswith("pg_") or 
                            name.startswith("sqlite_") or 
                            name.startswith("information_schema") or
                            name in ("sqlite_master", "sqlite_sequence")
                        ):
                            return False, f"Query violation: Access to system catalog table '{name}' is forbidden."

            return True, "SQL query is valid and safe to execute."

        except sqlglot.errors.ParseError as pe:
            logger.warning(f"SQL Syntax Parse Error: {pe}")
            return False, f"SQL Syntax Error: {str(pe)}"
        except Exception as e:
            logger.error(f"Unexpected validation error: {e}")
            return False, f"SQL Validation Exception: {str(e)}"

    def enforce_limit(self, sql: str, max_limit: int = settings.MAX_ROWS_LIMIT, dialect: str = "sqlite") -> str:
        """
        Parses the SQL and enforces a row limit directly in the AST.
        If a LIMIT is present and exceeds max_limit, it is set to max_limit.
        If no LIMIT is present, it is appended.
        """
        sqlglot_dialect = self._normalize_dialect(dialect)
        try:
            expression = sqlglot.parse_one(sql, read=sqlglot_dialect)
            
            # Ensure it is a select expression before injecting limit
            if isinstance(expression, (exp.Select, exp.Union)):
                limit_node = expression.args.get("limit")
                if limit_node:
                    try:
                        limit_val = int(limit_node.expression.name)
                        if limit_val > max_limit:
                            # Replace existing limit value
                            limit_node.expression.replace(exp.Literal.number(max_limit))
                    except Exception:
                        # Fallback rewrite
                        limit_node.replace(exp.Limit(expression=exp.Literal.number(max_limit)))
                else:
                    # Append limit node via method chaining
                    expression = expression.limit(max_limit)
                    
            return expression.sql(dialect=sqlglot_dialect)
        except Exception as e:
            logger.error(f"Failed to enforce limit via AST: {e}. Falling back to regex.")
            # Standard string fallback in case of parsing problems
            return self._regex_fallback_limit(sql, max_limit)

    def apply_rls(self, sql: str, rls_policies: list, dialect: str = "sqlite") -> str:
        """
        Parses SQL and replaces tables with filtered subqueries according to active RLS policies.
        rls_policies: List of RLSPolicy db objects.
        """
        if not rls_policies:
            return sql
            
        sqlglot_dialect = self._normalize_dialect(dialect)
        try:
            expression = sqlglot.parse_one(sql, read=sqlglot_dialect)
            
            # Map table names to policies for faster lookup
            policy_map = {p.table_name.lower(): p.filter_clause for p in rls_policies}
            
            # Walk AST to find Table nodes and replace them with subqueries
            tables_to_replace = []
            for node in expression.walk():
                if isinstance(node, exp.Table):
                    tbl_name = node.name.lower()
                    if tbl_name in policy_map:
                        # Avoid matching Table node inside the replacement subquery itself
                        parent = node.parent
                        is_already_subquery = False
                        while parent:
                            if isinstance(parent, exp.Subquery) and parent.alias == node.name:
                                is_already_subquery = True
                                break
                            parent = parent.parent
                        if not is_already_subquery:
                            tables_to_replace.append(node)
                            
            for node in tables_to_replace:
                tbl_name = node.name.lower()
                filter_clause = policy_map[tbl_name]
                subquery_sql = f"(SELECT * FROM {node.name} WHERE {filter_clause}) AS {node.name}"
                subquery_node = sqlglot.parse_one(subquery_sql, read=sqlglot_dialect)
                node.replace(subquery_node)
                
            return expression.sql(dialect=sqlglot_dialect)
        except Exception as e:
            logger.error(f"Failed to apply RLS: {e}")
            return sql

    def _normalize_dialect(self, dialect: str) -> str:
        """Map connection URI schemes to standard sqlglot dialect keys."""
        d = dialect.lower()
        if "postgres" in d:
            return "postgres"
        if "sqlite" in d:
            return "sqlite"
        if "mysql" in d:
            return "mysql"
        if "oracle" in d:
            return "oracle"
        return "sql"

    def _regex_fallback_limit(self, sql: str, limit: int) -> str:
        import re
        cleaned_sql = sql.strip().rstrip(";")
        limit_match = re.search(r"\blimit\s+(\d+)\b", cleaned_sql, re.IGNORECASE)
        if limit_match:
            current_limit = int(limit_match.group(1))
            if current_limit > limit:
                return re.sub(r"\blimit\s+(\d+)\b", f"LIMIT {limit}", cleaned_sql, flags=re.IGNORECASE) + ";"
            return sql
        else:
            return f"{cleaned_sql} LIMIT {limit};"

query_validator = QueryValidatorService()
