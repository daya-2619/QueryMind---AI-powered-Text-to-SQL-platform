import os
import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "storage", "query_cache")

def save_query_result_cache(history_id: int, columns: List[str], rows: List[Dict[str, Any]]) -> bool:
    """Saves the complete list of rows to a local JSON cache file to handle large datasets."""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        filepath = os.path.join(CACHE_DIR, f"{history_id}.json")
        data = {
            "columns": columns,
            "rows": rows
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Failed to save query result cache for history ID {history_id}: {e}")
        return False

def get_query_result_cache_page(history_id: int, page: int, limit: int) -> Optional[Dict[str, Any]]:
    """Retrieves a specific page of results from the cached JSON file."""
    try:
        filepath = os.path.join(CACHE_DIR, f"{history_id}.json")
        if not os.path.exists(filepath):
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        rows = data.get("rows", [])
        columns = data.get("columns", [])
        total_rows = len(rows)
        
        start_idx = (page - 1) * limit
        end_idx = page * limit
        page_rows = rows[start_idx:end_idx]
        
        return {
            "columns": columns,
            "rows": page_rows,
            "total_rows": total_rows,
            "row_count": len(page_rows)
        }
    except Exception as e:
        logger.error(f"Failed to read query result cache for history ID {history_id}: {e}")
        return None
