from fastapi import APIRouter
from app.api.endpoints import (
    query, schema, auth, history, saved, 
    users, databases, roles, security, monitoring, manager, analyst
)

api_router = APIRouter()

# Include sub-routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(query.router, prefix="/query", tags=["Query Execution"])
api_router.include_router(schema.router, prefix="/schema", tags=["Schema Intelligence"])
api_router.include_router(history.router, prefix="/history", tags=["Query History"])
api_router.include_router(saved.router, prefix="/saved", tags=["Saved Queries"])
api_router.include_router(users.router, prefix="/users", tags=["Admin User Management"])
api_router.include_router(databases.router, prefix="/databases", tags=["Admin Database Management"])
api_router.include_router(roles.router, prefix="/roles", tags=["Admin Role Management"])
api_router.include_router(security.router, prefix="/security", tags=["Admin Security Configurations"])
api_router.include_router(monitoring.router, prefix="/monitoring", tags=["Admin Monitoring Tools"])
api_router.include_router(manager.router, prefix="/manager", tags=["Manager Actions"])
api_router.include_router(analyst.router, prefix="/analyst", tags=["Analyst Actions"])
