from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

# Setup engine for Metadata database (SQLite by default, or Postgres)
connect_args = {}
if settings.METADATA_DATABASE_URL.startswith("sqlite"):
    # sqlite needs this to allow multi-thread access in development
    connect_args = {"check_same_thread": False}

metadata_engine = create_engine(
    settings.METADATA_DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=metadata_engine
)

Base = declarative_base()

def get_metadata_db():
    """FastAPI dependency to yield a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_active_connection_url(db) -> str:
    """Helper to dynamically fetch the active registered database target connection URL."""
    from app.models.rbac import DatabaseConfig
    from app.core.config import settings
    db_config = db.query(DatabaseConfig).filter(DatabaseConfig.is_active == True).order_by(DatabaseConfig.id.desc()).first()
    if db_config:
        return db_config.connection_url
    return settings.TARGET_DATABASE_URL

