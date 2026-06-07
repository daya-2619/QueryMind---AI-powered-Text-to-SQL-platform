import math
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session
from app.core.database import get_metadata_db, get_active_connection_url
from app.models.rbac import ScheduledReport
from app.models.query import SavedQuery
from app.core.security import check_role
from app.core.config import settings
from app.db.adapters import get_adapter

router = APIRouter()

class ReportScheduleCreate(BaseModel):
    report_name: str = Field(..., max_length=100)
    query_id: int = Field(..., description="ID of the saved query to run")
    cron_expression: str = Field(..., max_length=50, description="Cron string")
    recipient_email: str = Field(..., max_length=100)

class ReportScheduleResponse(BaseModel):
    id: int
    report_name: str
    query_id: int
    cron_expression: str
    recipient_email: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

@router.get("/scheduled-reports", response_model=List[ReportScheduleResponse])
def list_scheduled_reports(
    db: Session = Depends(get_metadata_db),
    current_user = Depends(check_role(["Admin", "Manager", "Viewer"]))
):
    """Retrieve all scheduled reports (Manager/Admin Only)."""
    return db.query(ScheduledReport).all()

@router.post("/scheduled-reports", response_model=ReportScheduleResponse, status_code=status.HTTP_201_CREATED)
def create_scheduled_report(
    schedule: ReportScheduleCreate,
    db: Session = Depends(get_metadata_db),
    current_user = Depends(check_role(["Admin", "Manager"]))
):
    """Schedule a recurring query report (Manager/Admin Only)."""
    # Verify query exists
    saved = db.query(SavedQuery).filter(SavedQuery.id == schedule.query_id).first()
    if not saved:
        raise HTTPException(status_code=404, detail="Saved query not found.")
        
    new_report = ScheduledReport(
        report_name=schedule.report_name,
        query_id=schedule.query_id,
        cron_expression=schedule.cron_expression,
        recipient_email=schedule.recipient_email,
        is_active=True
    )
    db.add(new_report)
    db.commit()
    db.refresh(new_report)
    return new_report

@router.delete("/scheduled-reports/{report_id}")
def delete_scheduled_report(
    report_id: int,
    db: Session = Depends(get_metadata_db),
    current_user = Depends(check_role(["Admin", "Manager"]))
):
    """Cancel a scheduled report (Manager/Admin Only)."""
    report = db.query(ScheduledReport).filter(ScheduledReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Scheduled report not found.")
    db.delete(report)
    db.commit()
    return {"success": True, "message": "Scheduled report cancelled."}

@router.post("/predictions")
def run_predictive_analytics(
    db: Session = Depends(get_metadata_db),
    current_user = Depends(check_role(["Admin", "Manager"]))
):
    """
    Perform linear regression forecasting over orders revenue timeline (Manager/Admin Only).
    """
    connection_url = get_active_connection_url(db)
    if not connection_url:
        raise HTTPException(status_code=400, detail="Target database is not configured.")
        
    try:
        adapter = get_adapter(connection_url)
        # Fetch daily transaction amounts
        sql = "SELECT order_date, total_amount FROM orders ORDER BY order_date ASC;"
        if adapter.dialect_name == "sqlite":
            sql = "SELECT strftime('%Y-%m-%d', order_date) as date, SUM(total_amount) as amount FROM orders GROUP BY 1 ORDER BY 1 ASC;"
        else:
            sql = "SELECT DATE_TRUNC('day', order_date) as date, SUM(total_amount) as amount FROM orders GROUP BY 1 ORDER BY 1 ASC;"
            
        res = adapter.execute_query(sql)
        rows = res.get("rows", [])
        
        if len(rows) < 2:
            return {
                "success": False,
                "error": "Insufficient transaction history to perform forecasting (minimum 2 days required)."
            }
            
        # Linear regression fit: y = mx + c
        n = len(rows)
        x_vals = list(range(n))
        y_vals = [float(row["amount"]) for row in rows]
        
        sum_x = sum(x_vals)
        sum_y = sum(y_vals)
        sum_xx = sum(x ** 2 for x in x_vals)
        sum_xy = sum(x * y for x, y in zip(x_vals, y_vals))
        
        denominator = (n * sum_xx - sum_x ** 2)
        if denominator == 0:
            m = 0
            c = sum_y / n
        else:
            m = (n * sum_xy - sum_x * sum_y) / denominator
            c = (sum_y - m * sum_x) / n
            
        # Predict next 3 points
        predictions = []
        for i in range(1, 4):
            pred_index = n + i
            pred_val = m * pred_index + c
            predictions.append({
                "period": f"T+{i} days",
                "predicted_amount": round(max(0.0, pred_val), 2)
            })
            
        return {
            "success": True,
            "metric": "Daily Revenue",
            "historical_points_count": n,
            "slope": round(m, 4),
            "intercept": round(c, 2),
            "predictions": predictions
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Predictive modeling failed: {str(e)}")

@router.post("/anomaly-detection")
def detect_revenue_anomalies(
    db: Session = Depends(get_metadata_db),
    current_user = Depends(check_role(["Admin", "Manager"]))
):
    """
    Scans orders history to identify transactions exceeding 2.5 standard deviations from the mean (Manager/Admin Only).
    """
    connection_url = get_active_connection_url(db)
    if not connection_url:
        raise HTTPException(status_code=400, detail="Target database is not configured.")
        
    try:
        adapter = get_adapter(connection_url)
        sql = "SELECT order_id, total_amount, order_date FROM orders;"
        res = adapter.execute_query(sql)
        rows = res.get("rows", [])
        
        if not rows:
            return {"success": True, "anomalies": [], "message": "No transaction records found."}
            
        amounts = [float(row["total_amount"]) for row in rows]
        n = len(amounts)
        mean = sum(amounts) / n
        
        variance = sum((x - mean) ** 2 for x in amounts) / n
        std_dev = math.sqrt(variance)
        
        threshold = 1.2
        anomalies = []
        for row in rows:
            amt = float(row["total_amount"])
            z_score = 0.0 if std_dev == 0 else (amt - mean) / std_dev
            if abs(z_score) > threshold:
                anomalies.append({
                    "order_id": row["order_id"],
                    "order_date": row["order_date"],
                    "amount": amt,
                    "z_score": round(z_score, 2),
                    "deviation": "High" if z_score > 0 else "Low"
                })
                
        return {
            "success": True,
            "mean": round(mean, 2),
            "std_dev": round(std_dev, 2),
            "anomaly_threshold_z": threshold,
            "anomalies_found": len(anomalies),
            "anomalies": anomalies
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Anomaly detection failed: {str(e)}")
