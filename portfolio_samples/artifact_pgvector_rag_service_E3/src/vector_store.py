"""Vector storage adapter supporting both PostgreSQL 18 pgvector on port 5433
and an in-memory normalized cosine similarity engine for zero-mock standalone execution.
Strict zero em dash policy enforced.
"""
import logging
import math
from typing import List, Dict, Any, Optional

import psycopg2
import psycopg2.extras
from psycopg2.extras import execute_values

from src.config import RAGConfig
from src.models import DocumentChunk, QueryResult, RAGResponse

logger = logging.getLogger("vector_store")


class PgVectorStore:
    def __init__(self, config: Optional[RAGConfig] = None):
        self.config = config or RAGConfig()
        self.corrupt_vectors_rejected: int = 0
        self.dimension_mismatches_detected: int = 0
        self.in_memory_chunks: Dict[str, DocumentChunk] = {}
        self.pg_available: bool = False
        self.pgvector_available: bool = False

    def validate_embedding(self, embedding: List[float]) -> bool:
        """Validates vector dimensionality and finite numeric values."""
        if not embedding or len(embedding) != self.config.embedding_dim:
            self.dimension_mismatches_detected += 1
            return False
        if any(math.isnan(v) or math.isinf(v) for v in embedding):
            self.corrupt_vectors_rejected += 1
            return False
        return True

    def init_database(self) -> bool:
        """Initializes PostgreSQL 18 schema and pgvector table if available,
        or configures in-memory cosine engine fallback.
        """
        try:
            conn = psycopg2.connect(
                host=self.config.db_host,
                port=self.config.db_port,
                user=self.config.db_user,
                password=self.config.db_password,
                dbname=self.config.db_name,
                connect_timeout=3,
            )
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(f"CREATE SCHEMA IF NOT EXISTS {self.config.db_schema};")
                # Attempt to register pgvector extension
                try:
                    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                    cur.execute(f"""
                        CREATE TABLE IF NOT EXISTS {self.config.db_schema}.rag_embeddings (
                            chunk_id TEXT PRIMARY KEY,
                            document_id TEXT NOT NULL,
                            content TEXT NOT NULL,
                            embedding vector({self.config.embedding_dim}),
                            metadata JSONB,
                            created_at TIMESTAMPTZ DEFAULT NOW()
                        );
                        CREATE INDEX IF NOT EXISTS idx_rag_embeddings_hnsw 
                        ON {self.config.db_schema}.rag_embeddings 
                        USING hnsw (embedding vector_cosine_ops)
                        WITH (m = 16, ef_construction = 64);
                    """)
                    self.pgvector_available = True
                    logger.info("PostgreSQL 18 pgvector HNSW table initialized successfully.")
                except Exception as ext_err:
                    logger.warning(f"pgvector extension not installed in PostgreSQL 18: {ext_err}. In-memory cosine engine active.")
                    self.pgvector_available = False

            conn.close()
            self.pg_available = True
            return True
        except Exception as conn_err:
            logger.info(f"PostgreSQL connection offline or port unreachable: {conn_err}. Standalone in-memory mode active.")
            self.pg_available = False
            self.pgvector_available = False
            return False

    def store_chunks(self, chunks: List[DocumentChunk]) -> int:
        """Stores document chunks into in-memory engine and PostgreSQL 18 if available."""
        valid_chunks: List[DocumentChunk] = []
        for chunk in chunks:
            if not self.validate_embedding(chunk.embedding):
                continue
            valid_chunks.append(chunk)
            self.in_memory_chunks[chunk.chunk_id] = chunk

        if not valid_chunks:
            return 0

        if self.pgvector_available:
            try:
                conn = psycopg2.connect(
                    host=self.config.db_host,
                    port=self.config.db_port,
                    user=self.config.db_user,
                    password=self.config.db_password,
                    dbname=self.config.db_name,
                )
                valid_records = [
                    (
                        c.chunk_id,
                        c.document_id,
                        c.content,
                        c.embedding,
                        psycopg2.extras.Json(c.metadata),
                    )
                    for c in valid_chunks
                ]
                query = f"""
                    INSERT INTO {self.config.db_schema}.rag_embeddings (
                        chunk_id, document_id, content, embedding, metadata
                    ) VALUES %s
                    ON CONFLICT (chunk_id) DO UPDATE SET
                        content = EXCLUDED.content,
                        embedding = EXCLUDED.embedding,
                        metadata = EXCLUDED.metadata;
                """
                with conn.cursor() as cur:
                    execute_values(cur, query, valid_records)
                conn.commit()
                conn.close()
            except Exception as e:
                logger.warning(f"PostgreSQL pgvector upsert failed, preserved in memory: {e}")

        return len(valid_chunks)

    def similarity_search(self, query_embedding: List[float], top_k: int = 5) -> List[QueryResult]:
        """Performs top-k similarity search via PostgreSQL pgvector HNSW or normalized cosine engine."""
        if not self.validate_embedding(query_embedding):
            return []

        if self.pgvector_available:
            try:
                conn = psycopg2.connect(
                    host=self.config.db_host,
                    port=self.config.db_port,
                    user=self.config.db_user,
                    password=self.config.db_password,
                    dbname=self.config.db_name,
                )
                query = f"""
                    SELECT chunk_id, content, (1 - (embedding <=> %s::vector)) AS score, metadata
                    FROM {self.config.db_schema}.rag_embeddings
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s;
                """
                results: List[QueryResult] = []
                with conn.cursor() as cur:
                    cur.execute(query, (query_embedding, query_embedding, top_k))
                    for row in cur.fetchall():
                        results.append(QueryResult(
                            chunk_id=row[0],
                            content=row[1],
                            similarity_score=float(row[2]),
                            metadata=row[3] or {},
                        ))
                conn.close()
                return results
            except Exception as e:
                logger.warning(f"PostgreSQL pgvector search query failed, using in-memory engine: {e}")

        # In-memory normalized cosine similarity engine
        q_norm = math.sqrt(sum(x * x for x in query_embedding))
        is_q_unit = abs(q_norm - 1.0) < 1e-4

        scored: List[QueryResult] = []
        for chunk in self.in_memory_chunks.values():
            c_emb = chunk.embedding
            if is_q_unit:
                # Fast dot product path for pre-normalized unit vectors
                dot = sum(a * b for a, b in zip(query_embedding, c_emb))
                sim = max(-1.0, min(1.0, dot))
            else:
                sim = RAGResponse.cosine_similarity(query_embedding, c_emb)
            scored.append(QueryResult(
                chunk_id=chunk.chunk_id,
                content=chunk.content,
                similarity_score=sim,
                metadata=chunk.metadata,
            ))

        scored.sort(key=lambda r: r.similarity_score, reverse=True)
        return scored[:top_k]
