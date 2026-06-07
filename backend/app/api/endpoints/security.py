from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session
from app.core.database import get_metadata_db
from app.models.rbac import DataMaskingRule, RLSPolicy
from app.core.security import check_role

router = APIRouter()

class MaskingRuleCreate(BaseModel):
    column_name: str = Field(..., max_length=50, description="Column name to mask")
    masking_pattern: str = Field("*****", max_length=50, description="Replacement pattern for masking")

class MaskingRuleResponse(BaseModel):
    id: int
    column_name: str
    masking_pattern: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

class RLSPolicyCreate(BaseModel):
    table_name: str = Field(..., max_length=50, description="Table name to restrict")
    filter_clause: str = Field(..., max_length=255, description="Filter criteria (e.g. city = 'Kolkata')")
    role: str = Field(..., max_length=20, description="Target role (Analyst, Viewer, etc.)")

class RLSPolicyResponse(BaseModel):
    id: int
    table_name: str
    filter_clause: str
    role: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

# Data Masking Endpoints
@router.get("/masking", response_model=List[MaskingRuleResponse])
def list_masking_rules(
    db: Session = Depends(get_metadata_db),
    current_user = Depends(check_role(["Admin"]))
):
    """List all registered data masking rules (Admin Only)."""
    return db.query(DataMaskingRule).all()

@router.post("/masking", response_model=MaskingRuleResponse, status_code=status.HTTP_201_CREATED)
def create_masking_rule(
    rule_create: MaskingRuleCreate,
    db: Session = Depends(get_metadata_db),
    current_user = Depends(check_role(["Admin"]))
):
    """Create a new column data masking rule (Admin Only)."""
    col_name = rule_create.column_name.strip().lower()
    existing = db.query(DataMaskingRule).filter(DataMaskingRule.column_name == col_name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Masking rule for this column already exists.")
        
    new_rule = DataMaskingRule(
        column_name=col_name,
        masking_pattern=rule_create.masking_pattern,
        is_active=True
    )
    db.add(new_rule)
    db.commit()
    db.refresh(new_rule)
    return new_rule

@router.delete("/masking/{rule_id}")
def delete_masking_rule(
    rule_id: int,
    db: Session = Depends(get_metadata_db),
    current_user = Depends(check_role(["Admin"]))
):
    """Delete a data masking rule configuration (Admin Only)."""
    rule = db.query(DataMaskingRule).filter(DataMaskingRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Masking rule not found.")
    db.delete(rule)
    db.commit()
    return {"success": True, "message": "Masking rule removed."}

# RLS Endpoints
@router.get("/rls", response_model=List[RLSPolicyResponse])
def list_rls_policies(
    db: Session = Depends(get_metadata_db),
    current_user = Depends(check_role(["Admin"]))
):
    """List all configured Row-Level Security policies (Admin Only)."""
    return db.query(RLSPolicy).all()

@router.post("/rls", response_model=RLSPolicyResponse, status_code=status.HTTP_201_CREATED)
def create_rls_policy(
    policy_create: RLSPolicyCreate,
    db: Session = Depends(get_metadata_db),
    current_user = Depends(check_role(["Admin"]))
):
    """Create a new Row-Level Security policy for a target role (Admin Only)."""
    role = policy_create.role.strip()
    if role not in ("Admin", "Manager", "Analyst", "Viewer"):
        raise HTTPException(status_code=400, detail="Target role must be a standard platform role.")
        
    new_policy = RLSPolicy(
        table_name=policy_create.table_name.strip().lower(),
        filter_clause=policy_create.filter_clause.strip(),
        role=role,
        is_active=True
    )
    db.add(new_policy)
    db.commit()
    db.refresh(new_policy)
    return new_policy

@router.delete("/rls/{policy_id}")
def delete_rls_policy(
    policy_id: int,
    db: Session = Depends(get_metadata_db),
    current_user = Depends(check_role(["Admin"]))
):
    """Delete a Row-Level Security policy configuration (Admin Only)."""
    policy = db.query(RLSPolicy).filter(RLSPolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="RLS policy not found.")
    db.delete(policy)
    db.commit()
    return {"success": True, "message": "RLS policy removed."}
