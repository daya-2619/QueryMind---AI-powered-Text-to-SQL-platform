from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session
from app.core.database import get_metadata_db
from app.models.rbac import DatabaseConfig
from app.core.security import check_role
from app.db.adapters import get_adapter
from app.services.schema_rag import schema_rag
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

class DatabaseCreate(BaseModel):
    name: str = Field(..., max_length=50, description="Friendly database name")
    connection_url: str = Field(..., max_length=255, description="Connection URL")
    provider: str = Field(..., description="postgresql, mysql, oracle, mssql, sqlite")

class DatabaseResponse(BaseModel):
    id: int
    name: str
    connection_url: str
    provider: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

@router.get("/", response_model=List[DatabaseResponse])
def list_databases(
    db: Session = Depends(get_metadata_db),
    current_user = Depends(check_role(["Admin"]))
):
    """List all registered database configurations (Admin Only)."""
    return db.query(DatabaseConfig).all()

@router.post("/", response_model=DatabaseResponse, status_code=status.HTTP_201_CREATED)
def create_database(
    db_create: DatabaseCreate,
    db: Session = Depends(get_metadata_db),
    current_user = Depends(check_role(["Admin"]))
):
    """Register a new database connection URL (Admin Only)."""
    # Quick dialect validation
    provider = db_create.provider.lower()
    if provider not in ("postgresql", "mysql", "oracle", "mssql", "sqlite"):
        raise HTTPException(status_code=400, detail="Unsupported database provider type.")
        
    # Mark all other configurations as inactive so the new one becomes the single active configuration
    try:
        db.query(DatabaseConfig).filter(DatabaseConfig.is_active == True).update({DatabaseConfig.is_active: False})
    except Exception as db_err:
        logger.error(f"Error resetting active database configurations: {db_err}")
        
    new_db = DatabaseConfig(
        name=db_create.name,
        connection_url=db_create.connection_url,
        provider=provider,
        is_active=True
    )
    db.add(new_db)
    db.commit()
    db.refresh(new_db)

    # Immediately rebuild Schema RAG vector index for this registered database data
    try:
        logger.info(f"Automatically synchronizing schema RAG index for newly registered database: {new_db.name}")
        schema_rag.build_index(new_db.connection_url)
    except Exception as sync_err:
        logger.error(f"Failed to auto-sync schema for newly registered database: {sync_err}")

    return new_db

@router.post("/{db_id}/test")
def test_database_connection(
    db_id: int,
    db: Session = Depends(get_metadata_db),
    current_user = Depends(check_role(["Admin"]))
):
    """Test connectivity to a registered database connection configuration (Admin Only)."""
    db_config = db.query(DatabaseConfig).filter(DatabaseConfig.id == db_id).first()
    if not db_config:
        raise HTTPException(status_code=404, detail="Database config not found.")
        
    try:
        adapter = get_adapter(db_config.connection_url)
        success = adapter.test_connection()
        return {
            "success": success,
            "message": "Connected successfully." if success else "Connection failed. Please check connection string, driver, or server availability."
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Connection test crashed: {str(e)}"
        }

@router.delete("/{db_id}")
def delete_database(
    db_id: int,
    db: Session = Depends(get_metadata_db),
    current_user = Depends(check_role(["Admin"]))
):
    """Delete database connection configuration (Admin Only)."""
    db_config = db.query(DatabaseConfig).filter(DatabaseConfig.id == db_id).first()
    if not db_config:
        raise HTTPException(status_code=404, detail="Database config not found.")
    db.delete(db_config)
    db.commit()
    return {"success": True, "message": "Database configuration removed."}
