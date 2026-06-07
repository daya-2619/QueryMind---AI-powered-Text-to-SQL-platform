import logging
from typing import Dict, List, Any, Optional
from app.db.adapters import get_adapter

logger = logging.getLogger(__name__)

class MetadataExtractorService:
    """Service to handle database metadata extraction, annotation, and caching."""
    
    def __init__(self):
        # In-memory cache for schema metadata to avoid hitting catalog frequently
        # Key: connection_url, Value: List of Table Metadata dicts
        self._schema_cache: Dict[str, List[Dict[str, Any]]] = {}

    def get_database_schema(self, connection_url: str, use_cache: bool = True) -> List[Dict[str, Any]]:
        """Retrieve schema metadata for a database connection."""
        if use_cache and connection_url in self._schema_cache:
            return self._schema_cache[connection_url]
            
        logger.info(f"Extracting metadata for database: {connection_url.split('@')[-1] if '@' in connection_url else connection_url}")
        adapter = get_adapter(connection_url)
        try:
            adapter.connect()
            schema = adapter.get_schema_metadata()
            self._schema_cache[connection_url] = schema
            return schema
        except Exception as e:
            logger.error(f"Failed to extract database metadata: {e}")
            raise e
        finally:
            adapter.disconnect()

    def clear_cache(self, connection_url: Optional[str] = None) -> None:
        """Clear schema cache, optionally for a specific database connection."""
        if connection_url:
            self._schema_cache.pop(connection_url, None)
        else:
            self._schema_cache.clear()

    @staticmethod
    def format_table_for_embeddings(table_meta: Dict[str, Any]) -> str:
        """
        Convert table and column metadata into a coherent text string.
        This string is used by the embedding model to create embeddings for Schema RAG.
        """
        name = table_meta["name"]
        description = table_meta.get("description", "") or f"Table {name}"
        
        columns_text = []
        for col in table_meta.get("columns", []):
            col_name = col["name"]
            data_type = col["data_type"]
            col_desc = col.get("description", "") or ""
            
            constraints = []
            if col.get("is_primary"):
                constraints.append("primary key")
            if col.get("is_foreign"):
                constraints.append(f"foreign key referencing {col.get('foreign_key_table')}({col.get('foreign_key_column')})")
            
            constraints_str = f" ({', '.join(constraints)})" if constraints else ""
            col_info = f"- {col_name} ({data_type}){constraints_str}: {col_desc}"
            columns_text.append(col_info)
            
        columns_block = "\n".join(columns_text)
        
        text_representation = (
            f"Table Name: {name}\n"
            f"Description: {description}\n"
            f"Columns:\n{columns_block}\n"
        )
        return text_representation

    @staticmethod
    def format_schema_for_prompt(tables_meta: List[Dict[str, Any]]) -> str:
        """
        Formats list of table metadata into an SQL DDL-like prompt context for the LLM.
        This provides the target structure for SQL generation.
        """
        prompt_parts = []
        for table in tables_meta:
            name = table["name"]
            desc = table.get("description", "")
            
            table_str = f"-- Table: {name}"
            if desc:
                table_str += f" | Description: {desc}"
            table_str += "\nCREATE TABLE " + name + " (\n"
            
            col_lines = []
            for col in table.get("columns", []):
                col_name = col["name"]
                data_type = col["data_type"]
                col_desc = col.get("description", "")
                
                # Format column line
                line = f"  {col_name} {data_type}"
                if col.get("is_primary"):
                    line += " PRIMARY KEY"
                if col.get("is_foreign"):
                    line += f" REFERENCES {col.get('foreign_key_table')}({col.get('foreign_key_column')})"
                
                if col_desc:
                    line += f" -- {col_desc}"
                col_lines.append(line)
                
            table_str += ",\n".join(col_lines)
            table_str += "\n);"
            prompt_parts.append(table_str)
            
        return "\n\n".join(prompt_parts)

metadata_extractor = MetadataExtractorService()
