"""Sliding-window text chunker with token boundary preservation and metadata injection.
Strict zero em dash policy enforced.
"""
import random
import re
from typing import List, Dict, Any, Optional, Callable

from src.models import DocumentChunk


class SlidingWindowChunker:
    """Sliding-window semantic chunker preserving token boundaries and injecting metadata."""

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
        embedding_dim: int = 384,
    ):
        self.chunk_size = max(1, chunk_size)
        self.chunk_overlap = max(0, min(chunk_overlap, self.chunk_size - 1))
        self.embedding_dim = embedding_dim

    def generate_deterministic_embedding(self, text: str) -> List[float]:
        """Generates a reproducible unit-length vector for deterministic testing and zero-mock pipelines."""
        if not text:
            return [0.0] * self.embedding_dim
        # Stable pseudo-random seed based on content hash
        stable_seed = abs(hash(text)) % 1000000
        rng = random.Random(stable_seed)
        raw_vec = [rng.uniform(-1.0, 1.0) for _ in range(self.embedding_dim)]
        norm = sum(x * x for x in raw_vec) ** 0.5
        return [x / norm for x in raw_vec] if norm > 0 else raw_vec

    def chunk_text(
        self,
        document_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        embedding_fn: Optional[Callable[[str], List[float]]] = None,
    ) -> List[DocumentChunk]:
        """Splits document text into overlapping token-boundary chunks with enriched metadata."""
        chunks: List[DocumentChunk] = []
        if not text or not text.strip():
            return chunks

        cleaned_text = re.sub(r"\s+", " ", text.strip())
        words = cleaned_text.split(" ")
        step = max(1, self.chunk_size - self.chunk_overlap)
        base_meta = dict(metadata or {})

        embed = embedding_fn or self.generate_deterministic_embedding
        chunk_idx = 0
        char_cursor = 0

        for i in range(0, len(words), step):
            chunk_words = words[i : i + self.config_chunk_size(len(words))]
            if not chunk_words:
                break

            content = " ".join(chunk_words)
            chunk_id = f"{document_id}_chk_{chunk_idx:04d}"

            # Calculate character offset boundaries
            char_start = text.find(chunk_words[0], char_cursor) if chunk_words else 0
            if char_start < 0:
                char_start = char_cursor
            char_end = char_start + len(content)
            char_cursor = max(char_cursor, char_start)

            chunk_meta = dict(base_meta)
            chunk_meta.update({
                "chunk_index": chunk_idx,
                "token_count": len(chunk_words),
                "char_start": char_start,
                "char_end": char_end,
                "document_id": document_id,
            })

            embedding = embed(content)

            chunks.append(DocumentChunk(
                chunk_id=chunk_id,
                document_id=document_id,
                content=content,
                embedding=embedding,
                metadata=chunk_meta,
                token_count=len(chunk_words),
            ))

            chunk_idx += 1
            if i + self.chunk_size >= len(words):
                break

        return chunks

    def config_chunk_size(self, total_words: int) -> int:
        return self.chunk_size
