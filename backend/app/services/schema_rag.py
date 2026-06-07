import os
import json
import logging
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from app.core.config import settings
from app.services.metadata_extractor import metadata_extractor

logger = logging.getLogger(__name__)

# Try importing FAISS and SentenceTransformers; support fallback if imports fail
try:
    import faiss
    HAS_FAISS = True
except ImportError:
    logger.warning("FAISS is not installed. Falling back to keyword search.")
    HAS_FAISS = False

try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    logger.warning("SentenceTransformers is not installed. Local embeddings will fall back.")
    HAS_SENTENCE_TRANSFORMERS = False


class SchemaRAGService:
    """Service to handle Schema Retrieval-Augmented Generation (RAG) using vector search."""

    def __init__(self):
        self.vector_db_path = settings.VECTOR_DB_PATH
        self._transformer_model = None
        self._active_schemas: Dict[str, List[Dict[str, Any]]] = {} # key: connection_url, val: tables metadata

    def _get_index_paths(self, connection_url: str) -> Tuple[str, str]:
        db_hash = str(abs(hash(connection_url)))
        map_path = os.path.join(self.vector_db_path, f"map_{db_hash}.json")
        index_path = os.path.join(self.vector_db_path, f"index_{db_hash}.faiss")
        return map_path, index_path

    def index_exists(self, connection_url: str) -> bool:
        map_path, index_path = self._get_index_paths(connection_url)
        if not os.path.exists(map_path):
            return False
        if HAS_FAISS and not os.path.exists(index_path):
            return False
        return True

    def _get_local_model(self):
        """Lazy load the sentence-transformer model to save memory on start."""
        global HAS_SENTENCE_TRANSFORMERS
        if not HAS_SENTENCE_TRANSFORMERS:
            raise ImportError("SentenceTransformers is not installed.")
        if self._transformer_model is None:
            logger.info(f"Loading local SentenceTransformer model: {settings.EMBEDDINGS_MODEL_NAME}")
            self._transformer_model = SentenceTransformer(settings.EMBEDDINGS_MODEL_NAME)
        return self._transformer_model

    def _generate_embeddings(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings based on configured provider."""
        if settings.EMBEDDINGS_PROVIDER == "local":
            model = self._get_local_model()
            embeddings = model.encode(texts, convert_to_numpy=True)
            return embeddings.astype('float32')
            
        elif settings.EMBEDDINGS_PROVIDER == "openai":
            if not settings.OPENAI_API_KEY:
                raise ValueError("OpenAI API Key is missing for embeddings generation.")
            from openai import OpenAI
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            response = client.embeddings.create(
                input=texts,
                model="text-embedding-3-small"
            )
            embeddings = [data.embedding for data in response.data]
            return np.array(embeddings, dtype='float32')
            
        elif settings.EMBEDDINGS_PROVIDER == "gemini":
            if not settings.GEMINI_API_KEY:
                raise ValueError("Gemini API Key is missing for embeddings generation.")
            import google.generativeai as genai
            genai.configure(api_key=settings.GEMINI_API_KEY)
            
            embeddings = []
            for text in texts:
                result = genai.embed_content(
                    model="models/text-embedding-004",
                    content=text,
                    task_type="RETRIEVAL_DOCUMENT"
                )
                embeddings.append(result['embedding'])
            return np.array(embeddings, dtype='float32')
        else:
            raise ValueError(f"Unknown embeddings provider: {settings.EMBEDDINGS_PROVIDER}")

    def build_index(self, connection_url: str) -> None:
        """
        Extracts schemas for a database connection, formats them,
        creates embeddings, and builds/saves the FAISS index.
        """
        # 1. Fetch tables metadata
        tables_meta = metadata_extractor.get_database_schema(connection_url, use_cache=False)
        self._active_schemas[connection_url] = tables_meta
        
        if not tables_meta:
            logger.warning("No tables found to index.")
            return

        # 2. Format each table into textual representations
        formatted_texts = [
            metadata_extractor.format_table_for_embeddings(table)
            for table in tables_meta
        ]
        
        # 3. Generate embeddings
        try:
            embeddings = self._generate_embeddings(formatted_texts)
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}. Falling back to basic cache indexing.")
            return

        # 4. Save metadata map and FAISS index
        os.makedirs(self.vector_db_path, exist_ok=True)
        
        # Save table mapping JSON
        db_hash = str(abs(hash(connection_url)))
        map_path = os.path.join(self.vector_db_path, f"map_{db_hash}.json")
        with open(map_path, "w", encoding="utf-8") as f:
            # Save mapping index to table details
            mapping = {str(i): table for i, table in enumerate(tables_meta)}
            json.dump(mapping, f, indent=2)

        # Build and write FAISS Index
        if HAS_FAISS:
            dim = embeddings.shape[1]
            index = faiss.IndexFlatIP(dim) # Cosine similarity (normalized inner product)
            # Normalize vectors for cosine similarity
            faiss.normalize_L2(embeddings)
            index.add(embeddings)
            
            index_path = os.path.join(self.vector_db_path, f"index_{db_hash}.faiss")
            faiss.write_index(index, index_path)
            logger.info(f"Successfully built and saved FAISS index for {connection_url.split('@')[-1] if '@' in connection_url else connection_url}")
        else:
            logger.warning("FAISS index not built (FAISS missing). Running on text cache fallback.")

    def retrieve_relevant_schema(self, connection_url: str, query: str, limit: int = settings.MAX_RELEVANT_TABLES) -> List[Dict[str, Any]]:
        """
        Retrieves top k tables relevant to user's question.
        Falls back to keyword matching if FAISS isn't available.
        Relational Expansion is applied to include immediate join neighbors.
        """
        map_path, index_path = self._get_index_paths(connection_url)
        
        # Ensure schema table mapping file exists
        if not os.path.exists(map_path):
            logger.info(f"Index files missing. Rebuilding index for connection.")
            self.build_index(connection_url)
            if not os.path.exists(map_path):
                # Fallback to direct schema reflection
                return metadata_extractor.get_database_schema(connection_url)

        with open(map_path, "r", encoding="utf-8") as f:
            mapping = json.load(f)

        retrieved_tables = []
        
        # If FAISS is not available or index building failed, use keyword/text search fallback
        if not HAS_FAISS or not os.path.exists(index_path):
            logger.info("Using keyword similarity fallback for schema retrieval.")
            retrieved_tables = self._fallback_keyword_search(mapping, query, limit)
        else:
            try:
                # 1. Generate query embedding
                query_emb = self._generate_embeddings([query])
                faiss.normalize_L2(query_emb)
                
                # 2. Load index and search
                index = faiss.read_index(index_path)
                
                # Clamp limit to size of database tables
                search_limit = min(limit, len(mapping))
                if search_limit > 0:
                    distances, indices = index.search(query_emb, search_limit)
                    
                    # 3. Collect tables
                    for i, idx in enumerate(indices[0]):
                        if idx == -1:
                            continue
                        score = float(distances[0][i])
                        # Filter by similarity threshold
                        if score >= settings.SIMILARITY_THRESHOLD:
                            table_meta = mapping[str(idx)]
                            retrieved_tables.append(table_meta)
                    
                    # Always ensure we return at least 1 table if the search was active
                    if not retrieved_tables and len(mapping) > 0:
                        retrieved_tables.append(mapping["0"])
            except Exception as e:
                logger.error(f"Error during vector search: {e}. Falling back to keyword search.")
                retrieved_tables = self._fallback_keyword_search(mapping, query, limit)

        # Apply Relational Neighbor Expansion (foreign key adjacent tables)
        expanded_tables = list(retrieved_tables)
        expanded_names = {t["name"].lower() for t in expanded_tables}
        
        for table_meta in list(retrieved_tables):
            t_name = table_meta["name"].lower()
            for key, other_table in mapping.items():
                ot_name = other_table["name"].lower()
                if ot_name in expanded_names:
                    continue
                # Check if other table references this table
                references_this = False
                for col in other_table.get("columns", []):
                    if col.get("is_foreign") and col.get("foreign_key_table", "").lower() == t_name:
                        references_this = True
                        break
                # Check if this table references other table
                this_references = False
                for col in table_meta.get("columns", []):
                    if col.get("is_foreign") and col.get("foreign_key_table", "").lower() == ot_name:
                        this_references = True
                        break
                        
                if references_this or this_references:
                    expanded_tables.append(other_table)
                    expanded_names.add(ot_name)
                    
        return expanded_tables

    def _fallback_keyword_search(self, mapping: Dict[str, Any], query: str, limit: int) -> List[Dict[str, Any]]:
        """A simple search matching keywords from the query to table and column names."""
        query_words = set(query.lower().split())
        scored_tables = []
        
        for key, table in mapping.items():
            name = table["name"].lower()
            desc = table.get("description", "").lower()
            
            score = 0
            # Table name match
            if name in query:
                score += 10
            for word in query_words:
                if word in name:
                    score += 5
                if word in desc:
                    score += 2
            
            # Column name match
            for col in table.get("columns", []):
                col_name = col["name"].lower()
                col_desc = col.get("description", "").lower()
                if col_name in query:
                    score += 5
                for word in query_words:
                    if word in col_name:
                        score += 2
                    if word in col_desc:
                        score += 0.5
            
            scored_tables.append((score, table))
            
        # Sort by score descending
        scored_tables.sort(key=lambda x: x[0], reverse=True)
        
        # Return top K tables
        results = [table for score, table in scored_tables[:limit] if score > 0 or len(query_words) == 0]
        
        # If no scores match, just return top tables by order up to limit
        if not results and len(mapping) > 0:
            results = [mapping[str(i)] for i in range(min(limit, len(mapping)))]
            
        return results

schema_rag = SchemaRAGService()
