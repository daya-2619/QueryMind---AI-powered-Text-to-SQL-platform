import os
import sys

from sqlalchemy import create_engine, text

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.api.endpoints.analyst import _build_schema_aware_widgets
from app.db.adapters import get_adapter
from app.services.metadata_extractor import metadata_extractor


def test_ai_dashboard_planner_uses_requested_table_and_real_columns(tmp_path):
    db_path = tmp_path / "dashboard.db"
    url = f"sqlite:///{db_path}"
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE dim_customers (
                customer_id INT,
                city TEXT,
                country TEXT,
                created_at TEXT,
                lifetime_value REAL
            );
            """
        ))
        conn.execute(text(
            """
            INSERT INTO dim_customers VALUES
            (1, 'Mumbai', 'India', '2026-01-03', 120.5),
            (2, 'Pune', 'India', '2026-02-04', 80.0),
            (3, 'Mumbai', 'India', '2026-02-10', 220.0);
            """
        ))
    engine.dispose()

    metadata_extractor.clear_cache(url)
    widgets = _build_schema_aware_widgets(
        "generate dashboard charts for dim_customers by city and lifetime value",
        url
    )

    assert widgets
    assert all("customers" not in widget["query"].replace("dim_customers", "") for widget in widgets)
    assert any('"dim_customers"' in widget["query"] for widget in widgets)
    assert any(widget.get("x_axis") == "city" for widget in widgets)
    assert any(widget.get("chart_type") == "line" and '"created_at"' in widget["query"] for widget in widgets)
    assert not any("STRFTIME('%Y-%m', \"lifetime_value\")" in widget["query"] for widget in widgets)

    adapter = get_adapter(url)
    try:
        for widget in widgets:
            result = adapter.execute_query(widget["query"])
            assert result["success"], result["error"]
    finally:
        adapter.disconnect()
