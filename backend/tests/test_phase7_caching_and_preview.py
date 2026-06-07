import os
import sys
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from app.core.database import Base, get_metadata_db
from app.core.config import settings

TEST_METADATA_DB = "./test_metadata_p7.db"
TEST_TARGET_DB = "./test_target_p7.db"

@pytest.fixture(scope="module")
def client():
    """Sets up a mock database environment for Phase 7 tests."""
    for db_f in (TEST_METADATA_DB, TEST_TARGET_DB):
        if os.path.exists(db_f):
            try:
                os.remove(db_f)
            except Exception:
                pass

    metadata_url = f"sqlite:///{TEST_METADATA_DB}"
    engine = create_engine(metadata_url, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Register core models
    Base.metadata.create_all(bind=engine)
    
    settings.METADATA_DATABASE_URL = metadata_url
    settings.TARGET_DATABASE_URL = f"sqlite:///{TEST_TARGET_DB}"
    
    target_engine = create_engine(settings.TARGET_DATABASE_URL)
    from sqlalchemy import text
    with target_engine.begin() as conn:
        conn.execute(text("CREATE TABLE mock_products (id INT PRIMARY KEY, title TEXT, price DECIMAL(10,2));"))
        # Insert 120 items to trigger caching and pagination
        for i in range(1, 121):
            conn.execute(text(f"INSERT INTO mock_products VALUES ({i}, 'Item {i}', {i * 1.5});"))
    target_engine.dispose()
    
    def override_get_metadata_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
            
    app.dependency_overrides[get_metadata_db] = override_get_metadata_db
    
    with TestClient(app) as c:
        yield c

    # Cleanup databases after test completes
    for db_f in (TEST_METADATA_DB, TEST_TARGET_DB):
        if os.path.exists(db_f):
            try:
                os.remove(db_f)
            except Exception:
                pass

def test_caching_and_preview_flow(client):
    # 1. Register and login Analyst user
    client.post("/api/v1/auth/register", json={"username": "analyst_p7", "password": "password123", "role": "Analyst"})
    auth_resp = client.post("/api/v1/auth/token", data={"username": "analyst_p7", "password": "password123"})
    assert auth_resp.status_code == 200
    token = auth_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Run query asking for all products (should trigger backend compilation, execute, and cache results)
    exec_resp = client.post(
        "/api/v1/query/execute",
        json={"sql": "SELECT * FROM mock_products;"},
        headers=headers
    )
    assert exec_resp.status_code == 200
    res_data = exec_resp.json()
    assert res_data["success"] is True
    assert "cache_id" in res_data
    assert res_data["total_row_count"] == 120
    # Rows should be truncated in initial response to 100
    assert len(res_data["rows"]) == 100
    
    cache_id = res_data["cache_id"]

    # 3. Test pagination retrieval
    # Page 1 (limit 50) -> should fetch 50 rows (rows 1-50)
    page1_resp = client.get(f"/api/v1/query/results/{cache_id}?page=1&limit=50", headers=headers)
    assert page1_resp.status_code == 200
    p1_data = page1_resp.json()
    assert len(p1_data["rows"]) == 50
    assert p1_data["rows"][0]["id"] == 1
    assert p1_data["rows"][-1]["id"] == 50

    # Page 2 (limit 50) -> should fetch rows 51-100
    page2_resp = client.get(f"/api/v1/query/results/{cache_id}?page=2&limit=50", headers=headers)
    assert page2_resp.status_code == 200
    p2_data = page2_resp.json()
    assert len(p2_data["rows"]) == 50
    assert p2_data["rows"][0]["id"] == 51
    assert p2_data["rows"][-1]["id"] == 100

    # Page 3 (limit 50) -> should fetch remaining rows 101-120
    page3_resp = client.get(f"/api/v1/query/results/{cache_id}?page=3&limit=50", headers=headers)
    assert page3_resp.status_code == 200
    p3_data = page3_resp.json()
    assert len(p3_data["rows"]) == 20
    assert p3_data["rows"][0]["id"] == 101
    assert p3_data["rows"][-1]["id"] == 120

    # 4. Test Table Preview
    preview_resp = client.get("/api/v1/schema/preview/mock_products?limit=10", headers=headers)
    assert preview_resp.status_code == 200
    preview_data = preview_resp.json()
    assert preview_data["success"] is True
    assert len(preview_data["rows"]) == 10
    assert "mock_products" not in preview_data["columns"] # Columns should contain field names like title, price
    assert "title" in preview_data["columns"]

    # 5. Verify SQL Injection check for invalid table name in preview
    invalid_resp = client.get("/api/v1/schema/preview/non_existent_table; SELECT * FROM mock_products;", headers=headers)
    assert invalid_resp.status_code == 404
