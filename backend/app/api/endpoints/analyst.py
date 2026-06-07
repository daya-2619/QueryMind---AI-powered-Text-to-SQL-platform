import re
from typing import List, Dict, Any, Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.security import check_role
from app.services.llm import llm_service
from app.services.schema_rag import schema_rag
from app.services.metadata_extractor import metadata_extractor
from app.core.config import settings
from app.core.database import get_metadata_db, get_active_connection_url
from app.db.adapters import get_adapter

router = APIRouter()

class DashboardPromptRequest(BaseModel):
    prompt: str = Field(..., description="Prompt describing the target dashboard (e.g. Sales KPI Overview)")

class VoiceQueryRequest(BaseModel):
    transcript: str = Field(..., description="Spoken question transcribed to text")

def _quote_identifier(identifier: str, dialect: str) -> str:
    escaped = identifier.replace("`", "``") if dialect == "mysql" else identifier.replace('"', '""')
    return f"`{escaped}`" if dialect == "mysql" else f'"{escaped}"'

def _column_names(table: Dict[str, Any]) -> List[str]:
    return [col["name"] for col in table.get("columns", [])]

def _column_type(table: Dict[str, Any], column_name: str) -> str:
    for col in table.get("columns", []):
        if col["name"] == column_name:
            return str(col.get("data_type", "")).lower()
    return ""

def _display_name(name: str) -> str:
    return name.replace("_", " ").title()

def _alias(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", name.lower()).strip("_")
    if not cleaned:
        return "value"
    if cleaned[0].isdigit():
        cleaned = f"value_{cleaned}"
    return cleaned

def _is_numeric_column(table: Dict[str, Any], column_name: str) -> bool:
    col_l = column_name.lower()
    col_type = _column_type(table, column_name)
    if col_l.endswith("_id") or col_l == "id":
        return False
    return any(token in col_type for token in ("int", "numeric", "decimal", "float", "double", "real", "money"))

def _is_date_column(table: Dict[str, Any], column_name: str) -> bool:
    col_l = column_name.lower()
    col_tokens = set(re.split(r"[_\W]+", col_l))
    col_type = _column_type(table, column_name)
    return (
        bool(col_tokens.intersection({"date", "time", "created", "updated", "timestamp", "month", "year"}))
        or any(token in col_type for token in ("date", "time"))
    )

def _is_dimension_column(table: Dict[str, Any], column_name: str) -> bool:
    col_l = column_name.lower()
    col_type = _column_type(table, column_name)
    if col_l.endswith("_id") or col_l == "id" or _is_date_column(table, column_name):
        return False
    if any(token in col_l for token in ("city", "country", "state", "region", "category", "status", "type", "segment", "name")):
        return True
    return any(token in col_type for token in ("char", "text", "string", "varchar"))

def _score_table_for_prompt(prompt: str, table: Dict[str, Any]) -> int:
    table_name = table["name"].lower()
    prompt_tokens = set(re.findall(r"[a-zA-Z0-9_]+", prompt.lower()))
    score = 0

    if table_name in prompt:
        score += 20
    for token in re.split(r"[_\W]+", table_name):
        if token and token in prompt_tokens:
            score += 5

    for col in table.get("columns", []):
        col_name = col["name"].lower()
        if col_name in prompt:
            score += 4
        for token in re.split(r"[_\W]+", col_name):
            if token and token in prompt_tokens:
                score += 1

    return score

def _select_dashboard_tables(prompt: str, schema: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    scored = [(table, _score_table_for_prompt(prompt, table)) for table in schema]
    matches = [table for table, score in sorted(scored, key=lambda item: item[1], reverse=True) if score > 0]
    if matches:
        return matches[:3]

    return schema[:3]

def _pick_columns_for_prompt(prompt: str, table: Dict[str, Any], columns: List[str], limit: int) -> List[str]:
    prompt_l = prompt.lower()
    scored: List[Tuple[str, int]] = []
    for col in columns:
        col_l = col.lower()
        score = 0
        if col_l in prompt_l:
            score += 10
        for token in re.split(r"[_\W]+", col_l):
            if token and token in prompt_l:
                score += 3
        if any(token in col_l for token in ("amount", "revenue", "sales", "price", "total")):
            score += 2
        if any(token in col_l for token in ("city", "country", "category", "status", "segment", "region")):
            score += 2
        scored.append((col, score))

    return [col for col, _ in sorted(scored, key=lambda item: item[1], reverse=True)[:limit]]

def _month_expression(column: str, dialect: str) -> str:
    quoted_col = _quote_identifier(column, dialect)
    if dialect == "sqlite":
        return f"strftime('%Y-%m', {quoted_col})"
    if dialect == "mysql":
        return f"DATE_FORMAT({quoted_col}, '%Y-%m')"
    return f"DATE_TRUNC('month', {quoted_col})"

def _find_column(table: Dict[str, Any], preferred: List[str], categories: List[str]) -> Optional[str]:
    columns = _column_names(table)
    lowered = {col.lower(): col for col in columns}
    for name in preferred:
        if name in lowered:
            return lowered[name]

    for col in columns:
        col_l = col.lower()
        col_type = _column_type(table, col)
        if "text" in categories and (
            any(token in col_l for token in ("city", "country", "state", "region", "category", "name", "type", "status"))
            or any(token in col_type for token in ("char", "text", "string"))
        ):
            return col
        if "number" in categories and (
            any(token in col_l for token in ("amount", "total", "revenue", "sales", "price", "cost", "qty", "quantity"))
            or any(token in col_type for token in ("int", "numeric", "decimal", "float", "double", "real"))
        ):
            return col
        if "date" in categories and (
            any(token in col_l for token in ("date", "time", "created", "month"))
            or any(token in col_type for token in ("date", "time"))
        ):
            return col
    return None

def _choose_table(prompt: str, schema: List[Dict[str, Any]], keywords: List[str]) -> Optional[Dict[str, Any]]:
    if not schema:
        return None

    prompt_tokens = set(re.findall(r"[a-zA-Z0-9_]+", prompt.lower()))
    for table in schema:
        table_name = table["name"].lower()
        if table_name in prompt_tokens or table_name in prompt:
            return table

    for table in schema:
        table_name = table["name"].lower()
        if any(keyword in table_name for keyword in keywords):
            return table

    return schema[0]

def _validate_widget_queries(widgets: List[Dict[str, Any]], dialect: str) -> List[Dict[str, Any]]:
    from app.services.query_validator import query_validator

    valid_widgets = []
    for widget in widgets:
        sql = widget.get("query", "")
        sanitized_sql = query_validator.enforce_limit(sql, dialect=dialect)
        is_safe, _ = query_validator.validate_sql(sanitized_sql, dialect=dialect)
        if is_safe:
            widget["query"] = sanitized_sql
            valid_widgets.append(widget)
    return valid_widgets

def _build_table_dashboard_widgets(prompt: str, table: Dict[str, Any], dialect: str) -> List[Dict[str, Any]]:
    table_name = table["name"]
    quoted_table = _quote_identifier(table_name, dialect)
    columns = _column_names(table)
    numeric_cols = [col for col in columns if _is_numeric_column(table, col)]
    dimension_cols = [col for col in columns if _is_dimension_column(table, col)]
    date_cols = [col for col in columns if _is_date_column(table, col)]

    numeric_cols = _pick_columns_for_prompt(prompt, table, numeric_cols, 3)
    dimension_cols = _pick_columns_for_prompt(prompt, table, dimension_cols, 3)
    date_cols = _pick_columns_for_prompt(prompt, table, date_cols, 1)

    widgets: List[Dict[str, Any]] = [
        {
            "title": f"Total {_display_name(table_name)}",
            "type": "metric",
            "query": f"SELECT COUNT(*) AS count FROM {quoted_table};",
            "width": 4
        }
    ]

    for numeric_col in numeric_cols[:2]:
        metric_alias = _alias(f"total_{numeric_col}")
        widgets.append({
            "title": f"Total {_display_name(numeric_col)}",
            "type": "metric",
            "query": f"SELECT SUM({_quote_identifier(numeric_col, dialect)}) AS {metric_alias} FROM {quoted_table};",
            "width": 4
        })

    if numeric_cols:
        avg_col = numeric_cols[0]
        avg_alias = _alias(f"avg_{avg_col}")
        widgets.append({
            "title": f"Average {_display_name(avg_col)}",
            "type": "metric",
            "query": f"SELECT AVG({_quote_identifier(avg_col, dialect)}) AS {avg_alias} FROM {quoted_table};",
            "width": 4
        })

    if date_cols:
        date_col = date_cols[0]
        metric_col = numeric_cols[0] if numeric_cols else None
        value_alias = _alias(f"total_{metric_col}") if metric_col else "count"
        aggregate = f"SUM({_quote_identifier(metric_col, dialect)})" if metric_col else "COUNT(*)"
        widgets.append({
            "title": f"Monthly {_display_name(metric_col or table_name)} Trend",
            "type": "chart",
            "chart_type": "line",
            "query": (
                f"SELECT {_month_expression(date_col, dialect)} AS month, {aggregate} AS {value_alias} "
                f"FROM {quoted_table} WHERE {_quote_identifier(date_col, dialect)} IS NOT NULL "
                f"GROUP BY 1 ORDER BY 1 ASC LIMIT 24;"
            ),
            "x_axis": "month",
            "y_axes": [value_alias],
            "width": 12
        })

    for dim_col in dimension_cols:
        dim_alias = _alias(dim_col)
        widgets.append({
            "title": f"Top {_display_name(dim_col)}",
            "type": "chart",
            "chart_type": "bar",
            "query": (
                f"SELECT {_quote_identifier(dim_col, dialect)} AS {dim_alias}, COUNT(*) AS count "
                f"FROM {quoted_table} WHERE {_quote_identifier(dim_col, dialect)} IS NOT NULL "
                f"GROUP BY {_quote_identifier(dim_col, dialect)} ORDER BY count DESC LIMIT 10;"
            ),
            "x_axis": dim_alias,
            "y_axes": ["count"],
            "width": 6
        })

    if numeric_cols and dimension_cols:
        dim_col = dimension_cols[0]
        num_col = numeric_cols[0]
        value_alias = _alias(f"total_{num_col}")
        dim_alias = _alias(dim_col)
        widgets.append({
            "title": f"{_display_name(num_col)} By {_display_name(dim_col)}",
            "type": "chart",
            "chart_type": "bar",
            "query": (
                f"SELECT {_quote_identifier(dim_col, dialect)} AS {dim_alias}, "
                f"SUM({_quote_identifier(num_col, dialect)}) AS {value_alias} "
                f"FROM {quoted_table} WHERE {_quote_identifier(dim_col, dialect)} IS NOT NULL "
                f"GROUP BY {_quote_identifier(dim_col, dialect)} ORDER BY {value_alias} DESC LIMIT 10;"
            ),
            "x_axis": dim_alias,
            "y_axes": [value_alias],
            "width": 6
        })

    return widgets

def _build_schema_aware_widgets(prompt: str, connection_url: str) -> List[Dict[str, Any]]:
    schema = metadata_extractor.get_database_schema(connection_url, use_cache=True)
    adapter = get_adapter(connection_url)
    dialect = adapter.dialect_name
    widgets: List[Dict[str, Any]] = []

    for table in _select_dashboard_tables(prompt, schema):
        widgets.extend(_build_table_dashboard_widgets(prompt, table, dialect))

    seen_queries = set()
    unique_widgets = []
    for widget in widgets:
        query = widget.get("query")
        if query and query not in seen_queries:
            seen_queries.add(query)
            unique_widgets.append(widget)

    return _validate_widget_queries(unique_widgets[:8], dialect)

@router.post("/ai-dashboard")
def generate_ai_dashboard_layout(
    req: DashboardPromptRequest,
    db: Session = Depends(get_metadata_db),
    current_user = Depends(check_role(["Admin", "Manager", "Analyst"]))
):
    """
    Generates a structured multi-widget dashboard configuration JSON from a description (Analyst/Manager/Admin Only).
    """
    prompt = req.prompt.lower()
    connection_url = get_active_connection_url(db)
    if not connection_url:
        raise HTTPException(status_code=400, detail="Database target is not configured.")

    widgets = _build_schema_aware_widgets(prompt, connection_url)
    if not widgets:
        raise HTTPException(status_code=400, detail="No tables were found in the active database schema.")
        
    return {
        "success": True,
        "dashboard_title": req.prompt.title(),
        "widgets_count": len(widgets),
        "widgets": widgets
    }

@router.post("/voice-to-sql")
def translate_voice_transcription(
    req: VoiceQueryRequest,
    db: Session = Depends(get_metadata_db),
    current_user = Depends(check_role(["Admin", "Manager", "Analyst"]))
):
    """
    Processes a voice transcription text and converts it to a SQL structured response (Analyst/Manager/Admin Only).
    """
    connection_url = get_active_connection_url(db)
    if not connection_url:
        raise HTTPException(status_code=400, detail="Database target is not configured.")
        
    try:
        # Extract schemas and compile using local translation fallback
        relevant_tables = schema_rag.retrieve_relevant_schema(connection_url, req.transcript)
        schema_ddl = metadata_extractor.format_schema_for_prompt(relevant_tables)
        
        result = llm_service.generate_sql_response(req.transcript, schema_ddl, connection_url=connection_url)
        return {
            "success": True,
            "transcript_parsed": req.transcript,
            "sql": result.get("sql"),
            "explanation": result.get("explanation"),
            "chart_recommendation": result.get("chart_recommendation")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Voice query processing failed: {str(e)}")
