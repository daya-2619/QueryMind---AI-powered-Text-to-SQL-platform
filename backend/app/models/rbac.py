from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, ForeignKey, func
from app.core.database import Base

class DatabaseConfig(Base):
    __tablename__ = "database_configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    connection_url = Column(String(255), nullable=False)
    provider = Column(String(20), nullable=False) # postgresql, mysql, oracle, mssql, sqlite
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

class CustomRole(Base):
    __tablename__ = "custom_roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(255), nullable=True)
    permissions = Column(JSON, nullable=False) # e.g. ["view_dashboards", "ask_ai", "execute_sql"]
    created_at = Column(DateTime, server_default=func.now())

class DataMaskingRule(Base):
    __tablename__ = "data_masking_rules"

    id = Column(Integer, primary_key=True, index=True)
    column_name = Column(String(50), nullable=False, index=True)
    masking_pattern = Column(String(50), default="*****", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

class RLSPolicy(Base):
    __tablename__ = "rls_policies"

    id = Column(Integer, primary_key=True, index=True)
    table_name = Column(String(50), nullable=False)
    filter_clause = Column(String(255), nullable=False) # e.g. "city = 'Kolkata'"
    role = Column(String(20), nullable=False) # Target role
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

class ScheduledReport(Base):
    __tablename__ = "scheduled_reports"

    id = Column(Integer, primary_key=True, index=True)
    report_name = Column(String(100), nullable=False)
    query_id = Column(Integer, ForeignKey("saved_queries.id"), nullable=False)
    cron_expression = Column(String(50), nullable=False) # e.g. "0 0 * * *"
    recipient_email = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
