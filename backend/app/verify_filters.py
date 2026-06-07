import json
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models.user import User
from app.models.query import QueryHistory

# Insert a failed query into metadata.db manually to test filtering
db = SessionLocal()
# Ensure we have at least one failed log in DB
failed_log = db.query(QueryHistory).filter(QueryHistory.success == False).first()
if not failed_log:
    print("No failed log found. Creating one...")
    new_failed = QueryHistory(
        session_id="test-failed-session",
        question="Select from invalid_table",
        generated_sql="SELECT * FROM invalid_table;",
        execution_time_ms=5.0,
        row_count=0,
        success=False,
        error_message="Table not found"
    )
    db.add(new_failed)
    db.commit()
    print("Created failed log.")
else:
    print("Found existing failed log.")

# Create test client
client = TestClient(app)

# Login to get token
resp = client.post("/api/v1/auth/login", json={"username": "test_analyst", "password": "password123"})
if resp.status_code != 200:
    # If test_analyst doesn't exist, register it first
    client.post("/api/v1/auth/register", json={"username": "test_analyst", "password": "password123", "role": "Analyst"})
    resp = client.post("/api/v1/auth/login", json={"username": "test_analyst", "password": "password123"})

token = resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# 1. Fetch all
resp_all = client.get("/api/v1/history/?limit=50", headers=headers)
print("ALL LOGS:", len(resp_all.json()))

# 2. Fetch success only
resp_success = client.get("/api/v1/history/?limit=50&success=true", headers=headers)
print("SUCCESS LOGS:", len(resp_success.json()))
for item in resp_success.json()[:3]:
    print(f"  Question: {item['question']}, Success: {item['success']}")

# 3. Fetch failure only
resp_failure = client.get("/api/v1/history/?limit=50&success=false", headers=headers)
print("FAILURE LOGS:", len(resp_failure.json()))
for item in resp_failure.json()[:3]:
    print(f"  Question: {item['question']}, Success: {item['success']}")
