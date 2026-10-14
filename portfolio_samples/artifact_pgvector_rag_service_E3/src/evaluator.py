"""Hallucination detection and retrieval precision evaluator.
Strict zero em dash policy enforced.
"""
from typing import List
from src.models import QueryResult


class RAGEvaluator:
    def __init__(self):
        self.evaluations_run: int = 0

    def evaluate_response(self, answer: str, sources: List[QueryResult]) -> float:
        """Computes hallucination score from 0.0 (grounded) to 1.0 (unsupported hallucination)."""
        self.evaluations_run += 1
        if not answer or not sources:
            return 1.0

        answer_tokens = set(answer.lower().split())
        source_tokens = set()
        for src in sources:
            source_tokens.update(src.content.lower().split())

        overlap = answer_tokens.intersection(source_tokens)
        grounding_ratio = len(overlap) / len(answer_tokens) if answer_tokens else 0.0
        
        hallucination_score = max(0.0, 1.0 - grounding_ratio)
        return round(hallucination_score, 4)

    def detect_prompt_injection(self, user_query: str) -> bool:
        """Detects prompt injection attempts such as system instruction overrides."""
        lowered = user_query.lower()
        patterns = [
            "ignore previous instructions",
            "system prompt",
            "leak secret",
            "override role",
            "you are now a",
            "reveal credentials",
        ]
        return any(p in lowered for p in patterns)
