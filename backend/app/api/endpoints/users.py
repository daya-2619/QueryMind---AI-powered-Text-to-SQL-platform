from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.database import get_metadata_db
from app.models.user import User
from app.schemas.user import UserResponse, UserCreate
from app.core.security import get_password_hash, check_role

router = APIRouter()

class UserUpdate(BaseModel):
    role: Optional[str] = Field(None, description="Admin, Manager, Analyst, Viewer")
    is_active: Optional[bool] = Field(None, description="Active status")

class PasswordReset(BaseModel):
    new_password: str = Field(..., min_length=6, description="New password, min 6 chars")

@router.get("/", response_model=List[UserResponse])
def list_users(
    db: Session = Depends(get_metadata_db),
    current_user = Depends(check_role(["Admin"]))
):
    """Retrieve all registered users (Admin Only)."""
    return db.query(User).all()

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    user_in: UserCreate,
    db: Session = Depends(get_metadata_db),
    current_user = Depends(check_role(["Admin"]))
):
    """Create a new user manually with a defined role (Admin Only)."""
    existing_user = db.query(User).filter(User.username == user_in.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists.")
        
    hashed_pw = get_password_hash(user_in.password)
    role = user_in.role if user_in.role in ("Admin", "Manager", "Analyst", "Viewer") else "Viewer"
    new_user = User(
        username=user_in.username,
        hashed_password=hashed_pw,
        role=role,
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user_update: UserUpdate,
    db: Session = Depends(get_metadata_db),
    current_user = Depends(check_role(["Admin"]))
):
    """Update user role and active status (Admin Only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
        
    if user_update.role is not None:
        if user_update.role not in ("Admin", "Manager", "Analyst", "Viewer"):
            raise HTTPException(status_code=400, detail="Invalid role type.")
        user.role = user_update.role
        
    if user_update.is_active is not None:
        user.is_active = user_update.is_active
        
    db.commit()
    db.refresh(user)
    return user

@router.delete("/{user_id}", status_code=status.HTTP_200_OK)
def delete_user(
    user_id: int,
    db: Session = Depends(get_metadata_db),
    current_user = Depends(check_role(["Admin"]))
):
    """Delete a user account (Admin Only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    db.delete(user)
    db.commit()
    return {"success": True, "message": "User deleted successfully."}

@router.post("/{user_id}/disable", response_model=UserResponse)
def disable_user(
    user_id: int,
    db: Session = Depends(get_metadata_db),
    current_user = Depends(check_role(["Admin"]))
):
    """Disable a user account (Admin Only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    user.is_active = False
    db.commit()
    db.refresh(user)
    return user

@router.post("/{user_id}/reset-password", status_code=status.HTTP_200_OK)
def reset_password(
    user_id: int,
    reset: PasswordReset,
    db: Session = Depends(get_metadata_db),
    current_user = Depends(check_role(["Admin"]))
):
    """Force reset a user password (Admin Only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    user.hashed_password = get_password_hash(reset.new_password)
    db.commit()
    return {"success": True, "message": "User password reset successfully."}
