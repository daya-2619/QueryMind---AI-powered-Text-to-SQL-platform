import os
import sys
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Adjust paths
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from app.core.database import Base, get_metadata_db
from app.core.config import settings

# Test database file setup
TEST_METADATA_DB = "./test_metadata.db"
TEST_TARGET_DB = "./test_target.db"

@pytest.fixture(scope="module")
def client():
    """Create a test client with a clean temporary SQLite metadata and target database."""
    # Setup clean db files
    for db_f in (TEST_METADATA_DB, TEST_TARGET_DB):
        if os.path.exists(db_f):
            try:
                os.remove(db_f)
            except Exception:
                pass

    # Configure metadata DB engine
    metadata_url = f"sqlite:///{TEST_METADATA_DB}"
    engine = create_engine(metadata_url, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    # Overwrite configuration URLs for test runs
    settings.METADATA_DATABASE_URL = metadata_url
    settings.TARGET_DATABASE_URL = f"sqlite:///{TEST_TARGET_DB}"
    
    # Setup test target database table to execute against
    target_engine = create_engine(settings.TARGET_DATABASE_URL)
    from sqlalchemy import text
    with target_engine.begin() as conn:
        conn.execute(text("CREATE TABLE items (id INT, name TEXT);"))
        conn.execute(text("INSERT INTO items VALUES (1, 'Widget A'), (2, 'Widget B');"))
    target_engine.dispose()
    
    def override_get_metadata_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
            
    # Inject override
    app.dependency_overrides[get_metadata_db] = override_get_metadata_db
    
    with TestClient(app) as c:
        yield c
        
    # Clean up files
    app.dependency_overrides.clear()
    engine.dispose()
    for db_f in (TEST_METADATA_DB, TEST_TARGET_DB):
        if os.path.exists(db_f):
            try:
                os.remove(db_f)
            except Exception:
                pass

def test_user_registration_and_login(client):
    """Test user registration, duplicate checks, and JWT logins."""
    # 1. Register Admin (first user created in empty database defaults to Admin)
    resp = client.post("/api/v1/auth/register", json={
        "username": "admin1",
        "password": "password123",
        "role": "Admin"
    })
    assert resp.status_code == 201
    assert resp.json()["username"] == "admin1"
    assert resp.json()["role"] == "Admin"
    
    # 2. Register Analyst
    resp = client.post("/api/v1/auth/register", json={
        "username": "analyst1",
        "password": "password123",
        "role": "Analyst"
    })
    assert resp.status_code == 201
    
    # 3. Duplicate registration check
    resp_dup = client.post("/api/v1/auth/register", json={
        "username": "analyst1",
        "password": "password123",
        "role": "Analyst"
    })
    assert resp_dup.status_code == 400
    
    # 4. Login and extract token
    resp_login = client.post("/api/v1/auth/login", json={
        "username": "analyst1",
        "password": "password123"
    })
    assert resp_login.status_code == 200
    token_data = resp_login.json()
    assert "access_token" in token_data
    assert token_data["role"] == "Analyst"

def test_rbac_guards(client):
    """Verify that role limits are enforced on query ask endpoints."""
    # 1. Create Viewer
    client.post("/api/v1/auth/register", json={
        "username": "viewer1",
        "password": "password123",
        "role": "Viewer"
    })
    
    # Get Viewer token
    resp = client.post("/api/v1/auth/login", json={"username": "viewer1", "password": "password123"})
    viewer_token = resp.json()["access_token"]
    
    # Get Analyst token
    resp = client.post("/api/v1/auth/login", json={"username": "analyst1", "password": "password123"})
    analyst_token = resp.json()["access_token"]
    
    # 2. Viewer attempts to run a query (Viewer has read-only, not query permission)
    resp_view = client.post(
        "/api/v1/query/ask", 
        json={"question": "show all items"},
        headers={"Authorization": f"Bearer {viewer_token}"}
    )
    assert resp_view.status_code == 403 # Forbidden
    
    # 3. Analyst runs query (Analyst has execution rights)
    resp_analyst = client.post(
        "/api/v1/query/ask", 
        json={"question": "show all items"},
        headers={"Authorization": f"Bearer {analyst_token}"}
    )
    assert resp_analyst.status_code == 200

def test_history_logging_and_search(client):
    """Test that query execution is logged and searchable via history APIs."""
    # Get Analyst token
    resp = client.post("/api/v1/auth/login", json={"username": "analyst1", "password": "password123"})
    token = resp.json()["access_token"]
    
    # 1. Execute query to generate history logs
    client.post(
        "/api/v1/query/ask", 
        json={"question": "show all items", "session_id": "test-session-123"},
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # 2. Fetch history lists
    resp_hist = client.get(
        "/api/v1/history/?session_id=test-session-123",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp_hist.status_code == 200
    logs = resp_hist.json()
    assert len(logs) >= 1
    assert logs[0]["question"] == "show all items"
    assert logs[0]["session_id"] == "test-session-123"

    # 3. Test success status filtering on query logs
    resp_success = client.get(
        "/api/v1/history/?success=true",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp_success.status_code == 200
    for item in resp_success.json():
        assert item["success"] is True

    # 4. Test failure status filtering on query logs
    resp_failure = client.get(
        "/api/v1/history/?success=false",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp_failure.status_code == 200
    for item in resp_failure.json():
        assert item["success"] is False

def test_saved_queries_library(client):
    """Test creating, editing, and deleting query templates."""
    # Get Analyst token
    resp_login = client.post("/api/v1/auth/login", json={"username": "analyst1", "password": "password123"})
    analyst_token = resp_login.json()["access_token"]
    
    # Get Admin token
    resp_admin = client.post("/api/v1/auth/login", json={"username": "admin1", "password": "password123"})
    admin_token = resp_admin.json()["access_token"]
    
    # 1. Create saved query
    resp_create = client.post(
        "/api/v1/saved/",
        json={
            "title": "Items Query",
            "question": "show all items",
            "sql_query": "SELECT * FROM items;",
            "description": "Helper query"
        },
        headers={"Authorization": f"Bearer {analyst_token}"}
    )
    assert resp_create.status_code == 201
    saved_id = resp_create.json()["id"]
    
    # 2. View saved queries list
    resp_list = client.get("/api/v1/saved/", headers={"Authorization": f"Bearer {analyst_token}"})
    assert resp_list.status_code == 200
    assert len(resp_list.json()) >= 1
    
    # 3. Update saved query
    resp_update = client.put(
        f"/api/v1/saved/{saved_id}",
        json={
            "title": "Items Query Updated",
            "question": "show all items",
            "sql_query": "SELECT * FROM items LIMIT 10;",
            "description": "Updated"
        },
        headers={"Authorization": f"Bearer {analyst_token}"}
    )
    assert resp_update.status_code == 200
    assert resp_update.json()["title"] == "Items Query Updated"
    
    # 4. Try updating using a different Analyst (should fail)
    client.post("/api/v1/auth/register", json={
        "username": "analyst2",
        "password": "password123",
        "role": "Analyst"
    })
    resp_login2 = client.post("/api/v1/auth/login", json={"username": "analyst2", "password": "password123"})
    analyst2_token = resp_login2.json()["access_token"]
    
    resp_hack = client.put(
        f"/api/v1/saved/{saved_id}",
        json={
            "title": "Hacked",
            "question": "x",
            "sql_query": "x",
            "description": "x"
        },
        headers={"Authorization": f"Bearer {analyst2_token}"}
    )
    assert resp_hack.status_code == 403 # Forbidden
    
    # Admin is allowed to edit/delete any query template
    resp_admin_update = client.put(
        f"/api/v1/saved/{saved_id}",
        json={
            "title": "Items Query Admin Edit",
            "question": "show all items",
            "sql_query": "SELECT * FROM items;",
            "description": "Admin override"
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp_admin_update.status_code == 200
    
    # 5. Delete saved query template
    resp_del = client.delete(f"/api/v1/saved/{saved_id}", headers={"Authorization": f"Bearer {analyst_token}"})
    assert resp_del.status_code == 204
