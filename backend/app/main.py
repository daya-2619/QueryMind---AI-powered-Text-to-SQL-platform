import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.api import api_router
from app.services.schema_rag import schema_rag
from app.db.adapters import get_adapter
from app.core.database import Base, metadata_engine
from app.models.user import User
from app.models.query import QueryHistory, SavedQuery
from app.models.rbac import DatabaseConfig, CustomRole, DataMaskingRule, RLSPolicy, ScheduledReport

# Configure logging format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-initialize schema embeddings and connection adapter pools on start."""
    logger.info("Initializing Enterprise Text-to-SQL Analytics Platform...")
    
    # 0. Initialize database metadata tables
    logger.info("Creating platform metadata database tables...")
    Base.metadata.create_all(bind=metadata_engine)
    
    # 1. Inspect configured providers
    logger.info(f"Configured LLM: {settings.LLM_PROVIDER}")
    logger.info(f"Configured Embeddings: {settings.EMBEDDINGS_PROVIDER}")
    
    # 2. Verify target database connection and build index
    if settings.TARGET_DATABASE_URL:
        adapter = get_adapter(settings.TARGET_DATABASE_URL)
        logger.info("Verifying connection to target database...")
        if adapter.test_connection():
            logger.info("Target database connected successfully! Building/synchronizing Schema RAG vector index...")
            try:
                schema_rag.build_index(settings.TARGET_DATABASE_URL)
                logger.info("Schema RAG vector index initialized on startup.")
            except Exception as e:
                logger.error(f"Failed to build schema RAG index on startup: {e}")
        else:
            logger.error("Failed to connect to target database. Verify settings.TARGET_DATABASE_URL.")
    else:
        logger.warning("No TARGET_DATABASE_URL configured. Indexing deferred until first execution.")
    
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    description="Enterprise natural language to SQL analytics pipeline with schema intelligence RAG and visualizations.",
    lifespan=lifespan
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Attach API routes
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/health", tags=["System Health"])
def health_check():
    """Simple status check endpoint."""
    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "llm_provider": settings.LLM_PROVIDER,
        "embeddings_provider": settings.EMBEDDINGS_PROVIDER
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

