from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_metadata_db
from app.models.query import QueryHistory
from app.core.security import check_role

router = APIRouter()

@router.get("/metrics")
def get_query_metrics(
    db: Session = Depends(get_metadata_db),
    current_user = Depends(check_role(["Admin"]))
):
    """
    Retrieve aggregated platform metrics including query execution counts, 
    average latency, and translation accuracy (Admin Only).
    """
    total_queries = db.query(QueryHistory).count()
    if total_queries == 0:
        return {
            "total_queries": 0,
            "average_latency_ms": 0.0,
            "accuracy_rate": 100.0,
            "failed_queries": 0
        }
        
    avg_latency = db.query(func.avg(QueryHistory.execution_time_ms)).scalar() or 0.0
    successful_queries = db.query(QueryHistory).filter(QueryHistory.success == True).count()
    accuracy = (successful_queries / total_queries) * 100.0
    
    return {
        "total_queries": total_queries,
        "average_latency_ms": round(avg_latency, 2),
        "accuracy_rate": round(accuracy, 2),
        "failed_queries": total_queries - successful_queries
    }
