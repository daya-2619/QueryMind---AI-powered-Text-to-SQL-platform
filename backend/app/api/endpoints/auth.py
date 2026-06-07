from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.core.database import get_metadata_db
from app.core.config import settings
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, Token, LoginRequest
from app.core.security import get_password_hash, verify_password, create_access_token

router = APIRouter()

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user_in: UserCreate, db: Session = Depends(get_metadata_db)):
    """Registers a new account. Hashes passwords and saves metadata."""
    # Check if username exists
    existing_user = db.query(User).filter(User.username == user_in.username).first()
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Username already registered."
        )

    # Bootstrapping rule: If this is the first user registered in the system, default to Admin
    user_count = db.query(User).count()
    assigned_role = user_in.role
    if user_count == 0:
        assigned_role = "Admin"
    elif assigned_role not in ("Admin", "Manager", "Analyst", "Viewer"):
        assigned_role = "Viewer"

    hashed_pw = get_password_hash(user_in.password)
    new_user = User(
        username=user_in.username,
        hashed_password=hashed_pw,
        role=assigned_role
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.post("/login", response_model=Token)
def login_user(login_data: LoginRequest, db: Session = Depends(get_metadata_db)):
    """Authenticate credentials and generate a JWT access token."""
    user = db.query(User).filter(User.username == login_data.username).first()
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user account.")

    # Create token containing username sub claim and role claim
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role}
    )
    return Token(
        access_token=access_token,
        role=user.role,
        username=user.username
    )

@router.post("/token", response_model=Token)
def login_for_access_token_form(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_metadata_db)
):
    """Fallback standard OAuth2 password request form for API compatibility (e.g. Swagger UI)."""
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role}
    )
    return Token(
        access_token=access_token,
        role=user.role,
        username=user.username
    )
