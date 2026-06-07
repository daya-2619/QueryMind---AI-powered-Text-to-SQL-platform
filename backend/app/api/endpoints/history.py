from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_metadata_db
from app.models.query import QueryHistory
from app.schemas.query import QueryHistoryResponse
from app.core.security import check_role

router = APIRouter()

@router.get("/", response_model=List[QueryHistoryResponse])
def get_query_history(
    session_id: Optional[str] = Query(None, description="Filter logs by conversational session identifier"),
    success: Optional[bool] = Query(None, description="Filter by success or failure execution status"),
    search: Optional[str] = Query(None, description="Search keyword in questions or generated SQL statements"),
    limit: int = Query(50, ge=1, le=100, description="Max logs to return"),
    db: Session = Depends(get_metadata_db),
    current_user = Depends(check_role(["Admin", "Manager", "Analyst"]))
):
    """Retrieve query execution history logs with search filters."""
    query = db.query(QueryHistory)
    
    # 0. Enforce user restrictions: Analysts can only view their own history logs
    if current_user.role not in ("Admin", "Manager"):
        query = query.filter(QueryHistory.user_id == current_user.id)
        
    # 1. Apply session filter
    if session_id:
        query = query.filter(QueryHistory.session_id == session_id)
        
    # 2. Apply status filter
    if success is not None:
        query = query.filter(QueryHistory.success == success)
        
    # 3. Apply text search
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (QueryHistory.question.ilike(search_pattern)) | 
            (QueryHistory.generated_sql.ilike(search_pattern))
        )
        
    # 4. Sort chronologically (most recent first) and slice
    logs = query.order_by(QueryHistory.created_at.desc()).limit(limit).all()
    return logs
