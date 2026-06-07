import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_metadata_db, get_active_connection_url
from app.services.metadata_extractor import metadata_extractor
from app.services.schema_rag import schema_rag
from app.core.security import check_role
from app.schemas.query import ExecutionResultSchema
from app.db.adapters import get_adapter
from app.services.query_validator import query_validator

logger = logging.getLogger(__name__)

router = APIRouter()

class SyncRequest(BaseModel):
    connection_url: Optional[str] = Field(None, description="Database URL. If empty, uses default target database URL.")

@router.post("/sync")
def sync_schema(
    request: SyncRequest,
    db: Session = Depends(get_metadata_db),
    current_user = Depends(check_role(["Admin", "Manager", "Analyst"]))
):
    """
    Triggers schema metadata extraction and regenerates the FAISS vector database
    for Schema RAG lookup.
    """
    connection_url = request.connection_url or get_active_connection_url(db)
    if not connection_url:
        raise HTTPException(
            status_code=400,
            detail="Database connection URL is not configured."
        )
        
    try:
        logger.info(f"Triggering manual schema sync for target database.")
        # Rebuild FAISS Index (this automatically clears/reloads caches)
        schema_rag.build_index(connection_url)
        return {
            "success": True,
            "message": "Schema metadata and FAISS index synchronized successfully."
        }
    except Exception as e:
        logger.error(f"Failed to sync schema database: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Schema synchronization failed: {str(e)}"
        )

@router.get("/view", response_model=List[Dict[str, Any]])
def view_schema(
    connection_url: Optional[str] = None,
    db: Session = Depends(get_metadata_db),
    current_user = Depends(check_role(["Admin", "Manager", "Analyst"]))
):
    """
    Retrieve full database schema structure (tables, columns, types, keys)
    for target metadata explorer or ER diagram visualization.
    """
    target_url = connection_url or get_active_connection_url(db)
    if not target_url:
        raise HTTPException(
            status_code=400,
            detail="Database connection URL is not configured."
        )
        
    try:
        # Use cache for speedy loading of view
        schema = metadata_extractor.get_database_schema(target_url, use_cache=True)
        return schema
    except Exception as e:
        logger.error(f"Error fetching schema view: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/preview/{table_name}", response_model=ExecutionResultSchema)
def preview_table_data(
    table_name: str,
    limit: int = 50,
    db: Session = Depends(get_metadata_db),
    current_user = Depends(check_role(["Admin", "Manager", "Analyst"]))
):
    """
    Retrieve preview records (first N rows) for a given table from the
    currently active target database connection URL.
    """
    target_url = get_active_connection_url(db)
    if not target_url:
        raise HTTPException(
            status_code=400,
            detail="Database connection URL is not configured."
        )
        
    try:
        # 1. Fetch target schema and verify table exists to prevent SQL injection
        schema = metadata_extractor.get_database_schema(target_url, use_cache=True)
        table_names = [t["name"] for t in schema]
        logger.info(f"Preview check: requested '{table_name}', available tables: {table_names}")
        table_entry = next((t for t in schema if t["name"].lower() == table_name.lower()), None)
        if not table_entry:
            raise HTTPException(
                status_code=404,
                detail=f"Table '{table_name}' not found in the target database schema."
            )
            
        actual_table_name = table_entry["name"]
        
        # 2. Query target database using safe dialect-specific limits
        adapter = get_adapter(target_url)
        dialect = adapter.dialect_name
        
        # Build safe query
        sql_query = f"SELECT * FROM {actual_table_name}"
        sanitized_sql = query_validator.enforce_limit(sql_query, max_limit=limit, dialect=dialect)
        
        logger.info(f"User {current_user.username} previewing table '{actual_table_name}' using SQL: {sanitized_sql}")
        exec_data = adapter.execute_query(sanitized_sql)
        
        if not exec_data.get("success", False):
            raise HTTPException(
                status_code=500,
                detail=f"Database execution error: {exec_data.get('error')}"
            )
            
        rows = exec_data.get("rows", [])
        columns = exec_data.get("columns", [])
        
        # 3. Apply data masking rules for Analyst role if needed
        from app.models.rbac import DataMaskingRule
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
                logger.error(f"Error applying data masking to schema preview: {mask_err}")
                
        # Fetch actual total row count
        total_row_count = len(rows)
        try:
            count_query = f"SELECT COUNT(*) FROM \"{actual_table_name}\""
            count_res = adapter.execute_query(count_query)
            if count_res.get("success", False) and count_res.get("rows"):
                total_row_count = list(count_res["rows"][0].values())[0]
        except Exception as count_err:
            logger.error(f"Error counting table preview rows: {count_err}")

        return ExecutionResultSchema(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            execution_time_ms=exec_data.get("execution_time_ms", 0.0),
            success=True,
            error=None,
            total_row_count=total_row_count
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Failed to preview table data: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Schema preview failed: {str(e)}"
        )
