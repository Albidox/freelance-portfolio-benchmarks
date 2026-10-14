"""Async RAG pipeline orchestrator with document ingestion, similarity ranking,
and contextual prompt synthesis.
Strict zero em dash policy enforced.
"""
import random
import re
import time
from typing import List, Dict, Any, Optional

from src.config import RAGConfig
from src.models import DocumentChunk, QueryResult, RAGResponse
from src.vector_store import PgVectorStore
from src.evaluator import RAGEvaluator
from src.chunker import SlidingWindowChunker


class RAGPipeline:
    def __init__(
        self,
        config: Optional[RAGConfig] = None,
        vector_store: Optional[PgVectorStore] = None,
        chunker: Optional[SlidingWindowChunker] = None,
        evaluator: Optional[RAGEvaluator] = None,
    ):
        self.config = config or RAGConfig()
        self.vector_store = vector_store or PgVectorStore(self.config)
        self.chunker = chunker or SlidingWindowChunker(
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
            embedding_dim=self.config.embedding_dim,
        )
        self.evaluator = evaluator or RAGEvaluator()

    def generate_embedding(self, text: str) -> List[float]:
        """Generates a deterministic unit-length embedding vector."""
        if not text:
            return [0.0] * self.config.embedding_dim
        random.seed(hash(text) % 100000)
        raw_vec = [random.uniform(-1.0, 1.0) for _ in range(self.config.embedding_dim)]
        norm = sum(x * x for x in raw_vec) ** 0.5
        return [x / norm for x in raw_vec] if norm > 0 else raw_vec

    def chunk_text(self, document_id: str, text: str) -> List[DocumentChunk]:
        """Splits text into sliding-window chunks with normalized embeddings."""
        chunks: List[DocumentChunk] = []
        if not text or not text.strip():
            return chunks

        # Clean text and split by sentences/paragraphs
        cleaned = re.sub(r"\s+", " ", text.strip())
        words = cleaned.split(" ")
        step = max(1, self.config.chunk_size - self.config.chunk_overlap)

        chunk_idx = 0
        for i in range(0, len(words), step):
            chunk_words = words[i : i + self.config.chunk_size]
            if not chunk_words:
                break
            content = " ".join(chunk_words)
            chunk_id = f"{document_id}_chk_{chunk_idx:04d}"

            # Generate deterministic normalized embedding for testing
            embedding = self.generate_embedding(content)

            chunks.append(DocumentChunk(
                chunk_id=chunk_id,
                document_id=document_id,
                content=content,
                embedding=embedding,
                token_count=len(chunk_words),
            ))
            chunk_idx += 1
            if i + self.config.chunk_size >= len(words):
                break

        return chunks

    def synthesize_prompt(self, query: str, sources: List[QueryResult]) -> str:
        """Assembles context passages into a structured grounded prompt."""
        context_passages = [
            f"[{idx + 1}] (Score: {src.similarity_score:.3f}): {src.content}"
            for idx, src in enumerate(sources)
        ]
        context_block = "\n".join(context_passages) if context_passages else "No relevant context found."
        return (
            "System: You are an enterprise knowledge assistant. Answer the user query using ONLY the provided context.\n"
            f"Context:\n{context_block}\n\n"
            f"User Query: {query}\n\n"
            "Answer:"
        )

    async def ingest_document(
        self,
        document_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Ingests document by chunking, embedding, and storing in vector store."""
        chunks = self.chunk_text(document_id, content)
        if metadata:
            for chk in chunks:
                chk.metadata.update(metadata)
        return self.vector_store.store_chunks(chunks)

    async def query(self, query_text: str, top_k: Optional[int] = None) -> RAGResponse:
        """Executes full RAG query lifecycle: injection check, similarity search,
        context synthesis, and hallucination scoring.
        """
        start = time.perf_counter()
        k = top_k or self.config.similarity_top_k

        if self.evaluator.detect_prompt_injection(query_text):
            latency = (time.perf_counter() - start) * 1000.0
            return RAGResponse(
                query=query_text,
                answer="Request rejected: security policy violation (prompt injection detected).",
                sources=[],
                latency_ms=latency,
                hallucination_score=1.0,
            )

        query_embedding = self.generate_embedding(query_text)
        sources = self.vector_store.similarity_search(query_embedding, top_k=k)

        if sources:
            # Deterministic synthesized response based on best match
            best_source = sources[0]
            answer = f"Based on verified documentation: {best_source.content}"
        else:
            answer = "No matching records located in knowledge vector repository."

        latency = (time.perf_counter() - start) * 1000.0
        h_score = self.evaluator.evaluate_response(answer, sources)

        return RAGResponse(
            query=query_text,
            answer=answer,
            sources=sources,
            latency_ms=latency,
            hallucination_score=h_score,
        )
