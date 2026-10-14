"""Configuration definitions for pgvector RAG microservice.
Strict zero em dash policy enforced.
"""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class RAGConfig:
    db_host: str = os.getenv("PGHOST", "127.0.0.1")
    db_port: int = int(os.getenv("PGPORT", "5433"))
    db_user: str = os.getenv("PGUSER", "postgres")
    db_password: str = os.getenv("PGPASSWORD", "postgres")
    db_name: str = os.getenv("PGDATABASE", "postgres")
    db_schema: str = os.getenv("PGSCHEMA", "sandbox_e3")
    
    embedding_dim: int = int(os.getenv("EMBEDDING_DIM", "384"))
    similarity_top_k: int = int(os.getenv("TOP_K", "5"))
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "512"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "64"))
    max_memory_mb: int = int(os.getenv("MAX_MEMORY_MB", "250"))
    request_timeout: float = float(os.getenv("REQUEST_TIMEOUT", "10.0"))
