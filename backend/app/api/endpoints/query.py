import uuid
import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_metadata_db, get_active_connection_url
from app.core.cache import save_query_result_cache
from app.models.query import QueryHistory
from app.models.rbac import RLSPolicy, DataMaskingRule
from app.schemas.query import QueryRequest, QueryResponse, ExecutionResultSchema, SQLExecuteRequest
from app.services.schema_rag import schema_rag
from app.services.metadata_extractor import metadata_extractor
from app.services.llm import llm_service
from app.services.query_validator import query_validator
from app.db.adapters import get_adapter
from app.core.security import get_current_user, check_role

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/ask", response_model=QueryResponse)
def ask_question(
    request: QueryRequest,
    db: Session = Depends(get_metadata_db),
    current_user = Depends(check_role(["Admin", "Manager", "Analyst"]))
):
    """
    Core pipeline to convert natural language question to SQL, execute it, 
    explain it, suggest charts, load database conversational memory, and log results.
    """
    # 1. Resolve connection URL and Target Database
    connection_url = request.connection_url or get_active_connection_url(db)
    if not connection_url:
        raise HTTPException(
            status_code=400, 
            detail="Database connection URL is not configured."
        )

    # 2. Manage or create conversation session ID
    session_id = request.session_id or str(uuid.uuid4())
    
    # 3. Load chat history from QueryHistory table in DB to feed conversational context
    chat_history = []
    try:
        db_history = db.query(QueryHistory)\
            .filter(QueryHistory.session_id == session_id)\
            .order_by(QueryHistory.created_at.asc())\
            .limit(6)\
            .all()
            
        for item in db_history:
            chat_history.append({"role": "user", "content": item.question})
            if item.generated_sql:
                chat_history.append({
                    "role": "assistant", 
                    "content": f"Generated SQL: {item.generated_sql}."
                })
    except Exception as he:
        logger.warning(f"Failed to load conversational memory from database: {he}. Operating without context.")

    try:
        # 4. Retrieve relevant schema context via Schema RAG
        logger.info(f"Retrieving schema context for question: '{request.question}'")
        relevant_tables = schema_rag.retrieve_relevant_schema(connection_url, request.question)
        
        # 5. Format tables to DDL
        schema_ddl = metadata_extractor.format_schema_for_prompt(relevant_tables)

        # 6. Call LLM to generate SQL, explanation, and visualization
        llm_output = llm_service.generate_sql_response(
            question=request.question,
            schema_ddl=schema_ddl,
            chat_history=chat_history,
            connection_url=connection_url
        )
        
        generated_sql = llm_output.get("sql")
        explanation = llm_output.get("explanation", {})
        chart_rec = llm_output.get("chart_recommendation", {})
        
        execution_result = None
        
        # 7. Validate and execute generated SQL
        if generated_sql:
            adapter = get_adapter(connection_url)
            dialect = adapter.dialect_name
            
            # Enforce limits and sanitize
            sanitized_sql = query_validator.enforce_limit(generated_sql, dialect=dialect)
            
            # Retrieve and apply active RLS policies
            try:
                rls_policies = db.query(RLSPolicy).filter(
                    RLSPolicy.role == current_user.role,
                    RLSPolicy.is_active == True
                ).all()
                sanitized_sql = query_validator.apply_rls(sanitized_sql, rls_policies, dialect=dialect)
            except Exception as rls_err:
                logger.error(f"Error applying RLS policies: {rls_err}")
            
            # Run safety checks
            is_safe, validation_msg = query_validator.validate_sql(sanitized_sql, dialect=dialect)
            
            if is_safe:
                logger.info(f"Executing SQL query: {sanitized_sql}")
                exec_data = adapter.execute_query(sanitized_sql)
                
                rows = exec_data.get("rows", [])
                columns = exec_data.get("columns", [])
                
                # Apply data masking rules for non-privileged roles (Viewer, Analyst)
                if current_user.role not in ("Admin", "Manager"):
                    try:
                        masking_rules = db.query(DataMaskingRule).filter(DataMaskingRule.is_active == True).all()
                        if masking_rules and rows:
                            for rule in masking_rules:
                                target_col = rule.column_name.lower()
                                for c in columns:
                                    if c.lower() == target_col:
                                        for row in rows:
                                            if c in row:
                                                row[c] = rule.masking_pattern
                    except Exception as mask_err:
                        logger.error(f"Error applying data masking rules: {mask_err}")
                
                execution_result = ExecutionResultSchema(
                    columns=columns,
                    rows=rows,
                    row_count=len(rows),
                    execution_time_ms=exec_data.get("execution_time_ms", 0.0),
                    success=exec_data.get("success", False),
                    error=exec_data.get("error")
                )
            else:
                logger.warning(f"SQL validation rejected query: {validation_msg}")
                execution_result = ExecutionResultSchema(
                    success=False,
                    error=f"SQL Security Validation Failed: {validation_msg}"
                )
        else:
            # Handle cases where LLM fails to output SQL
            execution_result = ExecutionResultSchema(
                success=False,
                error="LLM failed to generate a valid SQL query."
            )

        # 8. Record session conversation log in database query_history
        try:
            user_id = getattr(current_user, "id", None)
            log_entry = QueryHistory(
                user_id=user_id,
                session_id=session_id,
                question=request.question,
                generated_sql=generated_sql,
                execution_time_ms=execution_result.execution_time_ms if execution_result else 0.0,
                row_count=execution_result.row_count if execution_result else 0,
                success=execution_result.success if execution_result else False,
                error_message=execution_result.error if execution_result else "LLM translation failed",
                chart_type=chart_rec.get("chart_type") if chart_rec else None
            )
            db.add(log_entry)
            db.commit()
            db.refresh(log_entry)
            
            # Cache the full execution result to handle large datasets and truncate response payload
            if execution_result and execution_result.success:
                save_query_result_cache(log_entry.id, execution_result.columns, execution_result.rows)
                execution_result.cache_id = log_entry.id
                execution_result.total_row_count = len(execution_result.rows)
                if len(execution_result.rows) > 100:
                    execution_result.rows = execution_result.rows[:100]
                    execution_result.row_count = 100
        except Exception as le:
            logger.error(f"Failed to write execution log and cache results: {le}")

        # Return response
        return QueryResponse(
            session_id=session_id,
            question=request.question,
            sql=generated_sql,
            explanation=explanation,
            chart_recommendation=chart_rec,
            execution_result=execution_result
        )

    except Exception as e:
        logger.error(f"Error in ask_question pipeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute", response_model=ExecutionResultSchema)
def execute_sql(
    request: SQLExecuteRequest,
    db: Session = Depends(get_metadata_db),
    current_user = Depends(check_role(["Admin", "Manager", "Analyst"]))
):
    """
    Direct SQL execution endpoint with security validator, RLS, and data masking (Admin/Manager/Analyst Only).
    """
    connection_url = request.connection_url or get_active_connection_url(db)
    if not connection_url:
        raise HTTPException(status_code=400, detail="Database connection URL is not configured.")

    try:
        adapter = get_adapter(connection_url)
        dialect = adapter.dialect_name
        sql = request.sql

        # Enforce limits and sanitize
        sanitized_sql = query_validator.enforce_limit(sql, dialect=dialect)

        # Retrieve and apply active RLS policies
        rls_policies = db.query(RLSPolicy).filter(
            RLSPolicy.role == current_user.role,
            RLSPolicy.is_active == True
        ).all()
        sanitized_sql = query_validator.apply_rls(sanitized_sql, rls_policies, dialect=dialect)

        # Run safety checks
        is_safe, validation_msg = query_validator.validate_sql(sanitized_sql, dialect=dialect)
        if not is_safe:
            return ExecutionResultSchema(
                success=False,
                error=f"SQL Security Validation Failed: {validation_msg}",
                columns=[],
                rows=[],
                row_count=0,
                execution_time_ms=0.0
            )

        logger.info(f"Executing raw SQL query: {sanitized_sql}")
        exec_data = adapter.execute_query(sanitized_sql)
        rows = exec_data.get("rows", [])
        columns = exec_data.get("columns", [])

        # Apply data masking rules for Analyst
        if current_user.role not in ("Admin", "Manager"):
            masking_rules = db.query(DataMaskingRule).filter(DataMaskingRule.is_active == True).all()
            if masking_rules and rows:
                for rule in masking_rules:
                    target_col = rule.column_name.lower()
                    for c in columns:
                        if c.lower() == target_col:
                            for row in rows:
                                if c in row:
                                    row[c] = rule.masking_pattern

        # Log query execution in history for the user
        user_id = getattr(current_user, "id", None)
        log_entry = QueryHistory(
            user_id=user_id,
            session_id=f"direct-{uuid.uuid4()}",
            question=f"Raw SQL: {sql[:100]}",
            generated_sql=sanitized_sql,
            execution_time_ms=exec_data.get("execution_time_ms", 0.0),
            row_count=len(rows),
            success=exec_data.get("success", False),
            error_message=exec_data.get("error")
        )
        db.add(log_entry)
        db.commit()
        db.refresh(log_entry)

        # Cache results for pagination support
        if exec_data.get("success", False):
            save_query_result_cache(log_entry.id, columns, rows)
            
        total_rows = len(rows)
        # Truncate returned rows
        rows_truncated = rows[:100] if total_rows > 100 else rows

        return ExecutionResultSchema(
            columns=columns,
            rows=rows_truncated,
            row_count=len(rows_truncated),
            execution_time_ms=exec_data.get("execution_time_ms", 0.0),
            success=exec_data.get("success", False),
            error=exec_data.get("error"),
            cache_id=log_entry.id,
            total_row_count=total_rows
        )
    except Exception as e:
        logger.error(f"Error in execute_sql: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/results/{history_id}", response_model=ExecutionResultSchema)
def get_paginated_results(
    history_id: int,
    page: int = 1,
    limit: int = 50,
    db: Session = Depends(get_metadata_db),
    current_user = Depends(check_role(["Admin", "Manager", "Analyst"]))
):
    """
    Retrieve cached query execution results paginated (Admin/Manager/Analyst).
    Handles large datasets by loading chunked data from storage.
    """
    from app.core.cache import get_query_result_cache_page
    
    # Verify the log entry exists and belongs to the user if they are an Analyst
    log_entry = db.query(QueryHistory).filter(QueryHistory.id == history_id).first()
    if not log_entry:
        raise HTTPException(status_code=404, detail="Execution result log not found.")
        
    if current_user.role not in ("Admin", "Manager") and log_entry.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: You can only access your own query results.")
        
    cache_data = get_query_result_cache_page(history_id, page, limit)
    if cache_data is None:
        # Fallback: execute query again if cache file is missing
        if not log_entry.generated_sql:
            raise HTTPException(status_code=404, detail="Result cache file not found and SQL is empty.")
            
        connection_url = get_active_connection_url(db)
        try:
            adapter = get_adapter(connection_url)
            exec_data = adapter.execute_query(log_entry.generated_sql)
            if not exec_data.get("success", False):
                raise HTTPException(status_code=500, detail=f"Failed to execute query fallback: {exec_data.get('error')}")
            
            # Save cache file
            save_query_result_cache(history_id, exec_data["columns"], exec_data["rows"])
            
            # Get the page
            cache_data = get_query_result_cache_page(history_id, page, limit)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to rebuild result cache: {str(e)}")
            
    return ExecutionResultSchema(
        columns=cache_data["columns"],
        rows=cache_data["rows"],
        row_count=cache_data["row_count"],
        execution_time_ms=0.0,
        success=True,
        cache_id=history_id,
        total_row_count=cache_data["total_rows"]
    )

