from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session
from app.core.database import get_metadata_db
from app.models.rbac import CustomRole
from app.core.security import check_role

router = APIRouter()

class CustomRoleCreate(BaseModel):
    name: str = Field(..., max_length=50, description="Custom role name")
    description: str = Field(..., max_length=255, description="Role description")
    permissions: List[str] = Field(..., description="List of permissions keys (e.g. view_dashboards, ask_ai)")

class CustomRoleResponse(BaseModel):
    id: int
    name: str
    description: str
    permissions: List[str]

    model_config = ConfigDict(from_attributes=True)

@router.get("/", response_model=List[CustomRoleResponse])
def list_custom_roles(
    db: Session = Depends(get_metadata_db),
    current_user = Depends(check_role(["Admin"]))
):
    """List all configured custom roles (Admin Only)."""
    return db.query(CustomRole).all()

@router.post("/", response_model=CustomRoleResponse, status_code=status.HTTP_201_CREATED)
def create_custom_role(
    role_create: CustomRoleCreate,
    db: Session = Depends(get_metadata_db),
    current_user = Depends(check_role(["Admin"]))
):
    """Create a new custom role with explicit permissions (Admin Only)."""
    # Prevent overwriting system roles
    name = role_create.name.strip()
    if name.lower() in ("admin", "manager", "analyst", "viewer"):
        raise HTTPException(status_code=400, detail="Cannot override core system roles.")
        
    existing = db.query(CustomRole).filter(CustomRole.name == name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Role name already exists.")
        
    new_role = CustomRole(
        name=name,
        description=role_create.description,
        permissions=role_create.permissions
    )
    db.add(new_role)
    db.commit()
    db.refresh(new_role)
    return new_role

@router.delete("/{role_id}")
def delete_custom_role(
    role_id: int,
    db: Session = Depends(get_metadata_db),
    current_user = Depends(check_role(["Admin"]))
):
    """Delete a custom role (Admin Only)."""
    role = db.query(CustomRole).filter(CustomRole.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Custom role not found.")
    db.delete(role)
    db.commit()
    return {"success": True, "message": "Custom role removed."}
