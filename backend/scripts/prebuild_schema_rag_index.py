import logging
import os
import sys

# Ensure the backend root is on sys.path when the script is executed from scripts/.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.services.schema_rag import schema_rag

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)


def main() -> int:
    target_url = settings.TARGET_DATABASE_URL
    if not target_url:
        logging.error("TARGET_DATABASE_URL is not configured. Set it in your environment or .env file before running this script.")
        return 1

    if schema_rag.index_exists(target_url):
        logging.info("Schema RAG index already exists for target database. Skipping prebuild.")
        return 0

    logging.info("Prebuilding Schema RAG FAISS index for target database...")
    try:
        schema_rag.build_index(target_url)
    except Exception as exc:
        logging.error(f"Index prebuild failed: {exc}")
        return 2

    logging.info("Schema RAG index prebuild complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
