"""Data contracts and schemas for FastAPI pgvector RAG microservice.
Strict zero em dash policy enforced.
"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
import math
from datetime import datetime, timezone


@dataclass
class DocumentChunk:
    chunk_id: str
    document_id: str
    content: str
    embedding: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)
    token_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class VectorEmbedding:
    vector_id: str
    embedding: List[float]
    dimension: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class QueryRequest:
    query: str
    top_k: int = 5
    score_threshold: float = 0.65
    filters: Optional[Dict[str, Any]] = None


@dataclass
class QueryResult:
    chunk_id: str
    content: str
    similarity_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RAGResponse:
    query: str
    answer: str
    sources: List[QueryResult]
    latency_ms: float
    hallucination_score: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def cosine_similarity(cls, vec_a: List[float], vec_b: List[float]) -> float:
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return max(-1.0, min(1.0, dot / (norm_a * norm_b)))
