from typing import Dict, List, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

class QueryRequest(BaseModel):
    question: str = Field(..., description="The natural language question to analyze")
    connection_url: Optional[str] = Field(None, description="Connection URL of the target database. If null, uses the default target database.")
    session_id: Optional[str] = Field(None, description="Optional session ID for conversational memory / continuous chats.")

class ExplanationSchema(BaseModel):
    business_summary: str = Field(..., description="Summary of the query in simple business language")
    technical_details: str = Field(..., description="Details of joins, filters, or aggregates applied")
    step_by_step: List[str] = Field(default=[], description="Step-by-step breakdown of what the SQL executes")

class ChartRecommendationSchema(BaseModel):
    recommended: bool = Field(..., description="Whether a chart visualization is recommended for this data")
    chart_type: Optional[str] = Field(None, description="The recommended chart type (bar, line, pie, area, scatter)")
    x_axis_column: Optional[str] = Field(None, description="The column name to map to the X-axis")
    y_axis_columns: List[str] = Field(default=[], description="The column name(s) to map to the Y-axis")
    reasoning: Optional[str] = Field(None, description="Reasoning for selecting this chart type")

class ExecutionResultSchema(BaseModel):
    columns: List[str] = Field(default=[], description="List of columns returned by the query")
    rows: List[Dict[str, Any]] = Field(default=[], description="List of data rows")
    row_count: int = Field(0, description="Total number of rows returned")
    execution_time_ms: float = Field(0.0, description="Query execution time in milliseconds")
    success: bool = Field(True, description="Whether the query executed successfully")
    error: Optional[str] = Field(None, description="Error message if execution failed")
    cache_id: Optional[int] = Field(None, description="ID of cache storage for loading subsequent pages")
    total_row_count: Optional[int] = Field(None, description="Total rows in database without truncation")

class QueryResponse(BaseModel):
    session_id: str = Field(..., description="Active session ID for follow-up questions")
    question: str = Field(..., description="The user's original question")
    sql: Optional[str] = Field(None, description="The generated SQL query")
    explanation: ExplanationSchema = Field(..., description="Natural language explanation of the generated SQL")
    chart_recommendation: ChartRecommendationSchema = Field(..., description="Recommended visualization setup")
    execution_result: Optional[ExecutionResultSchema] = Field(None, description="Data output from execution")


# --- New schemas for Saved Queries and Query History ---

class SavedQueryCreate(BaseModel):
    title: str = Field(..., max_length=100)
    question: str
    sql_query: str
    description: Optional[str] = None

class SavedQueryResponse(SavedQueryCreate):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class QueryHistoryResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    session_id: str
    question: str
    generated_sql: Optional[str] = None
    execution_time_ms: float
    row_count: int
    success: bool
    error_message: Optional[str] = None
    chart_type: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SQLExecuteRequest(BaseModel):
    sql: str
    connection_url: Optional[str] = Field(None, description="Optional connection URL of the target database.")

