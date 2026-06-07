from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_metadata_db, get_active_connection_url
from app.models.query import SavedQuery
from app.schemas.query import SavedQueryCreate, SavedQueryResponse
from app.core.security import get_current_user, check_role
from app.db.adapters import get_adapter
from app.core.config import settings
from app.services.query_validator import query_validator
from app.models.rbac import RLSPolicy, DataMaskingRule

router = APIRouter()

@router.get("/", response_model=List[SavedQueryResponse])
def get_saved_queries(
    db: Session = Depends(get_metadata_db),
    current_user = Depends(check_role(["Admin", "Manager", "Analyst", "Viewer"]))
):
    """Retrieve all saved queries in the system."""
    # Admins and Managers can see all saved queries. Analysts and Viewers can see all as well (shared list)
    saved_list = db.query(SavedQuery).order_by(SavedQuery.created_at.desc()).all()
    return saved_list

@router.post("/", response_model=SavedQueryResponse, status_code=status.HTTP_201_CREATED)
def create_saved_query(
    query_in: SavedQueryCreate,
    db: Session = Depends(get_metadata_db),
    current_user = Depends(check_role(["Admin", "Manager", "Analyst"]))
):
    """Save a query template."""
    new_saved = SavedQuery(
        user_id=current_user.id,
        title=query_in.title,
        question=query_in.question,
        sql_query=query_in.sql_query,
        description=query_in.description
    )
    db.add(new_saved)
    db.commit()
    db.refresh(new_saved)
    return new_saved

@router.put("/{query_id}", response_model=SavedQueryResponse)
def update_saved_query(
    query_id: int,
    query_in: SavedQueryCreate,
    db: Session = Depends(get_metadata_db),
    current_user = Depends(check_role(["Admin", "Manager", "Analyst"]))
):
    """Modify details of a saved query template."""
    saved = db.query(SavedQuery).filter(SavedQuery.id == query_id).first()
    if not saved:
        raise HTTPException(status_code=404, detail="Saved query not found.")
        
    # Standard role check: Analysts can only edit their own templates; Admin/Manager can edit any
    if current_user.role == "Analyst" and saved.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Analysts can only modify their own saved queries."
        )

    saved.title = query_in.title
    saved.question = query_in.question
    saved.sql_query = query_in.sql_query
    saved.description = query_in.description
    
    db.commit()
    db.refresh(saved)
    return saved

@router.delete("/{query_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saved_query(
    query_id: int,
    db: Session = Depends(get_metadata_db),
    current_user = Depends(check_role(["Admin", "Manager", "Analyst"]))
):
    """Delete a saved query template from the library."""
    saved = db.query(SavedQuery).filter(SavedQuery.id == query_id).first()
    if not saved:
        raise HTTPException(status_code=404, detail="Saved query not found.")
        
    # Analysts can only delete their own templates; Admin/Manager can delete any
    if current_user.role == "Analyst" and saved.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Analysts can only delete their own saved queries."
        )

    db.delete(saved)
    db.commit()
    return None

@router.post("/{query_id}/execute")
def execute_saved_query(
    query_id: int,
    db: Session = Depends(get_metadata_db),
    current_user = Depends(check_role(["Admin", "Manager", "Analyst", "Viewer"]))
):
    """Execute a saved query template securely (Admin/Manager/Analyst/Viewer)."""
    saved = db.query(SavedQuery).filter(SavedQuery.id == query_id).first()
    if not saved:
        raise HTTPException(status_code=404, detail="Saved query not found.")

    connection_url = get_active_connection_url(db)
    if not connection_url:
        raise HTTPException(status_code=400, detail="Target database is not configured.")

    try:
        adapter = get_adapter(connection_url)
        dialect = adapter.dialect_name
        sql = saved.sql_query

        # Apply RLS
        rls_policies = db.query(RLSPolicy).filter(
            RLSPolicy.role == current_user.role,
            RLSPolicy.is_active == True
        ).all()
        sql = query_validator.apply_rls(sql, rls_policies, dialect=dialect)

        # Execute
        exec_data = adapter.execute_query(sql)
        rows = exec_data.get("rows", [])
        columns = exec_data.get("columns", [])

        # Apply data masking for Analyst and Viewer
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

        return {
            "success": exec_data.get("success", False),
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "execution_time_ms": exec_data.get("execution_time_ms", 0.0),
            "error": exec_data.get("error")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute saved query: {str(e)}")

