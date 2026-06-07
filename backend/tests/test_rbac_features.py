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

TEST_METADATA_DB = "./test_metadata_rbac.db"
TEST_TARGET_DB = "./test_target_rbac.db"

@pytest.fixture(scope="module")
def client():
    """Sets up a clean mock metadata and target database for testing permissions."""
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
        conn.execute(text("CREATE TABLE items (id INT, name TEXT);"))
        conn.execute(text("INSERT INTO items VALUES (1, 'Widget A'), (2, 'Widget B');"))
        # Create a mock orders table for forecasting & anomalies
        conn.execute(text("CREATE TABLE orders (order_id INT, total_amount DECIMAL(10,2), order_date TIMESTAMP);"))
        conn.execute(text("INSERT INTO orders VALUES (101, 100.0, '2026-06-01 10:00:00');"))
        conn.execute(text("INSERT INTO orders VALUES (102, 150.0, '2026-06-02 10:00:00');"))
        conn.execute(text("INSERT INTO orders VALUES (103, 900.0, '2026-06-03 10:00:00');")) # Anomaly (std dev > 2.5)
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
        
    # Cleanup files after all tests run
    for db_f in (TEST_METADATA_DB, TEST_TARGET_DB):
        if os.path.exists(db_f):
            try:
                os.remove(db_f)
            except Exception:
                pass

def test_rbac_user_management(client):
    # 1. Create primary Admin user using open register
    client.post("/api/v1/auth/register", json={
        "username": "superadmin",
        "password": "adminpassword",
        "role": "Admin"
    })
    
    # Login as Admin to retrieve token
    admin_login = client.post("/api/v1/auth/login", json={"username": "superadmin", "password": "adminpassword"})
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    
    # 2. Admin creates a Viewer user
    user_res = client.post("/api/v1/users/", json={
        "username": "viewer_user",
        "password": "viewerpassword",
        "role": "Viewer"
    }, headers=admin_headers)
    assert user_res.status_code == 201
    viewer_id = user_res.json()["id"]
    
    # 3. Verify user list
    users_list = client.get("/api/v1/users/", headers=admin_headers)
    assert users_list.status_code == 200
    assert len(users_list.json()) >= 2
    
    # 4. Disable user
    disable_res = client.post(f"/api/v1/users/{viewer_id}/disable", headers=admin_headers)
    assert disable_res.status_code == 200
    assert disable_res.json()["is_active"] is False
    
    # Try to login with disabled user -> should fail
    login_failed = client.post("/api/v1/auth/login", json={"username": "viewer_user", "password": "viewerpassword"})
    assert login_failed.status_code == 400
    
    # Re-enable user
    enable_res = client.put(f"/api/v1/users/{viewer_id}", json={"is_active": True}, headers=admin_headers)
    assert enable_res.status_code == 200
    assert enable_res.json()["is_active"] is True
    
    # Reset password
    reset_res = client.post(f"/api/v1/users/{viewer_id}/reset-password", json={"new_password": "newpassword123"}, headers=admin_headers)
    assert reset_res.status_code == 200
    
    # Login with new password
    login_success = client.post("/api/v1/auth/login", json={"username": "viewer_user", "password": "newpassword123"})
    assert login_success.status_code == 200

def test_admin_rbac_and_databases_setup(client):
    # Retrieve Admin headers
    admin_login = client.post("/api/v1/auth/login", json={"username": "superadmin", "password": "adminpassword"})
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Create Manager and Analyst
    client.post("/api/v1/users/", json={"username": "mngr", "password": "mngrpassword", "role": "Manager"}, headers=admin_headers)
    client.post("/api/v1/users/", json={"username": "anlyst", "password": "anlystpassword", "role": "Analyst"}, headers=admin_headers)
    
    # 1. Manage Databases Connections
    db_res = client.post("/api/v1/databases/", json={
        "name": "Local SQLite db",
        "connection_url": settings.TARGET_DATABASE_URL,
        "provider": "sqlite"
    }, headers=admin_headers)
    assert db_res.status_code == 201
    db_id = db_res.json()["id"]
    
    # Test connection
    test_res = client.post(f"/api/v1/databases/{db_id}/test", headers=admin_headers)
    assert test_res.status_code == 200
    assert test_res.json()["success"] is True
    
    # 2. Custom Role Creation
    role_res = client.post("/api/v1/roles/", json={
        "name": "ComplianceManager",
        "description": "Custom role for data auditor",
        "permissions": ["view_audit_logs", "view_reports"]
    }, headers=admin_headers)
    assert role_res.status_code == 201
    assert "view_audit_logs" in role_res.json()["permissions"]

def test_data_masking_and_rls_policies(client):
    # Retrieve tokens
    admin_login = client.post("/api/v1/auth/login", json={"username": "superadmin", "password": "adminpassword"})
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
    
    analyst_login = client.post("/api/v1/auth/login", json={"username": "anlyst", "password": "anlystpassword"})
    analyst_headers = {"Authorization": f"Bearer {analyst_login.json()['access_token']}"}
    
    manager_login = client.post("/api/v1/auth/login", json={"username": "mngr", "password": "mngrpassword"})
    manager_headers = {"Authorization": f"Bearer {manager_login.json()['access_token']}"}

    viewer_login = client.post("/api/v1/auth/login", json={"username": "viewer_user", "password": "newpassword123"})
    viewer_headers = {"Authorization": f"Bearer {viewer_login.json()['access_token']}"}

    # 1. Define Column Masking Rule for column "name"
    mask_res = client.post("/api/v1/security/masking", json={
        "column_name": "name",
        "masking_pattern": "[CONFIDENTIAL]"
    }, headers=admin_headers)
    assert mask_res.status_code == 201
    
    # 2. Define RLS Policy for table "items" on Analyst role -> limit to ID=1
    rls_res = client.post("/api/v1/security/rls", json={
        "table_name": "items",
        "filter_clause": "id = 1",
        "role": "Analyst"
    }, headers=admin_headers)
    assert rls_res.status_code == 201

    # 3. Test View Schema: Viewer should be rejected, Analyst allowed
    schema_view_viewer = client.get("/api/v1/schema/view", headers=viewer_headers)
    assert schema_view_viewer.status_code == 403
    
    schema_view_analyst = client.get("/api/v1/schema/view", headers=analyst_headers)
    assert schema_view_analyst.status_code == 200

    # 4. Ask queries: Viewer should be rejected from querying
    ask_viewer = client.post("/api/v1/query/ask", json={"question": "show items"}, headers=viewer_headers)
    assert ask_viewer.status_code == 403

    # 5. Ask queries: Analyst query should trigger RLS (only ID=1 Widget A) and mask column "name"
    # Force local mode for offline deterministic SQL compilation
    settings.LLM_PROVIDER = "local"
    ask_analyst = client.post("/api/v1/query/ask", json={"question": "Show all items"}, headers=analyst_headers)
    assert ask_analyst.status_code == 200
    rows_analyst = ask_analyst.json()["execution_result"]["rows"]
    assert len(rows_analyst) == 1
    assert rows_analyst[0]["id"] == 1
    assert rows_analyst[0]["name"] == "[CONFIDENTIAL]"

    # 6. Ask queries: Manager has no RLS/masking rules applied.
    # Should see both ID=1 Widget A and ID=2 Widget B in cleartext.
    ask_manager = client.post("/api/v1/query/ask", json={"question": "Show all items"}, headers=manager_headers)
    assert ask_manager.status_code == 200
    rows_manager = ask_manager.json()["execution_result"]["rows"]
    assert len(rows_manager) == 2
    assert rows_manager[0]["name"] == "Widget A"
    assert rows_manager[1]["name"] == "Widget B"

def test_manager_and_analyst_features(client):
    analyst_login = client.post("/api/v1/auth/login", json={"username": "anlyst", "password": "anlystpassword"})
    analyst_headers = {"Authorization": f"Bearer {analyst_login.json()['access_token']}"}
    
    manager_login = client.post("/api/v1/auth/login", json={"username": "mngr", "password": "mngrpassword"})
    manager_headers = {"Authorization": f"Bearer {manager_login.json()['access_token']}"}

    admin_login = client.post("/api/v1/auth/login", json={"username": "superadmin", "password": "adminpassword"})
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    # 1. Analyst: AI Dashboard Generation layout mockup
    dashboard_res = client.post("/api/v1/analyst/ai-dashboard", json={"prompt": "create sales trends dashboard"}, headers=analyst_headers)
    assert dashboard_res.status_code == 200
    assert dashboard_res.json()["widgets_count"] > 0
    
    # 2. Analyst: Voice-to-SQL mockup
    voice_res = client.post("/api/v1/analyst/voice-to-sql", json={"transcript": "show all items"}, headers=analyst_headers)
    assert voice_res.status_code == 200
    assert voice_res.json()["sql"] is not None

    # 3. Manager: Scheduled Reports
    # Create saved query first
    sq = client.post("/api/v1/saved/", json={
        "title": "Daily Items Count",
        "question": "show total items",
        "sql_query": "SELECT COUNT(*) FROM items;",
        "description": "Cron checklist"
    }, headers=manager_headers)
    assert sq.status_code == 201
    sq_id = sq.json()["id"]

    sched_res = client.post("/api/v1/manager/scheduled-reports", json={
        "report_name": "Items count hourly report",
        "query_id": sq_id,
        "cron_expression": "0 * * * *",
        "recipient_email": "manager@enterprise.com"
    }, headers=manager_headers)
    assert sched_res.status_code == 201

    # 4. Manager: Predictive Analytics (Sales Forecasting)
    pred_res = client.post("/api/v1/manager/predictions", headers=manager_headers)
    assert pred_res.status_code == 200
    assert pred_res.json()["success"] is True
    assert len(pred_res.json()["predictions"]) == 3

    # 5. Manager: Anomaly Detection
    anomaly_res = client.post("/api/v1/manager/anomaly-detection", headers=manager_headers)
    assert anomaly_res.status_code == 200
    assert anomaly_res.json()["success"] is True
    assert anomaly_res.json()["anomalies_found"] == 1
    assert anomaly_res.json()["anomalies"][0]["order_id"] == 103 # The $900 order is the anomaly

    # 6. Admin Monitoring Metrics
    metrics_res = client.get("/api/v1/monitoring/metrics", headers=admin_headers)
    assert metrics_res.status_code == 200
    assert metrics_res.json()["total_queries"] > 0
