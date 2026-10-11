"""
Mock Job Generator for Telegram Lead Alert Bot.
Simulates a burst of 100 incoming job listings containing 30 duplicates and 70 unique leads.
Rule: Zero em dashes across all code, docstrings, and comments.
"""

from __future__ import annotations

import json
import random
import time
from typing import Any, Dict, List


def generate_job_burst(seed: int = 42) -> List[Dict[str, Any]]:
    """
    Generate a deterministic burst of 100 job listings:
    - Exactly 70 unique leads.
    - Exactly 30 duplicate leads (re-broadcasts of earlier leads).
    """
    rng = random.Random(seed)
    
    platforms = [
        "Upwork",
        "Reddit r/forhire",
        "HackerNews Who is Hiring",
        "Freelancer",
        "WeWorkRemotely"
    ]
    
    titles = [
        "Senior Java 21 Backend Engineer for High-Throughput Payment Gateway",
        "Spring Boot Microservices Architect for Fintech Migration",
        "PostgreSQL Performance Optimization and Slow Query Tuning Specialist",
        "Async Python FastApi Backend Developer for Realtime Lead Dashboard",
        "Telegram Automation Bot Developer for Lead Capture and Webhook Alerts",
        "Database Migration Disaster Recovery Expert: Flyway Schema Fix",
        "Distributed Systems Engineer: Kafka Event Sourcing Pipeline",
        "Hibernate JPA N+1 Query Regression Audit and EntityGraph Fix",
        "Docker and Kubernetes Deployment Automation for SaaS API",
        "Redis Caching Layer Architect for Sub-10ms Latency Requirements"
    ]
    
    budgets = [
        "$100 - $250 Fixed",
        "$500 - $1,200 Fixed",
        "$2,500 - $5,000 Fixed",
        "$60 - $90 / hr",
        "$100 - $150 / hr"
    ]

    unique_leads: List[Dict[str, Any]] = []
    base_time = time.time() - 300.0  # 5 minutes ago

    for i in range(1, 71):
        platform = platforms[(i - 1) % len(platforms)]
        title_core = titles[(i - 1) % len(titles)]
        title = f"{title_core} (Ref #{i:03d})"
        url = f"https://job-feed.example.org/{platform.lower().replace(' ', '-')}/lead-{i:04d}"
        budget = budgets[(i - 1) % len(budgets)]
        detected_at = time.strftime(
            "%Y-%m-%d %H:%M:%S", time.gmtime(base_time + (i * 2))
        )
        description = (
            f"Looking for specialist to resolve {title_core.lower()}. "
            f"Must demonstrate immediate production experience and minimal safe diffs."
        )

        unique_leads.append({
            "platform": platform,
            "title": title,
            "url": url,
            "budget": budget,
            "description": description,
            "detected_at": detected_at,
            "client_id": f"client_{i:03d}"
        })

    # Select 30 duplicates from the 70 unique leads
    duplicate_leads: List[Dict[str, Any]] = []
    for j in range(30):
        # Pick from the first 30 unique leads to guarantee they were created earlier
        original = unique_leads[j]
        duplicate_item = dict(original)
        # Sligthly newer detected_at representing repeated crawl/poll
        duplicate_item["detected_at"] = time.strftime(
            "%Y-%m-%d %H:%M:%S", time.gmtime(base_time + 150.0 + (j * 2))
        )
        duplicate_leads.append(duplicate_item)

    # Interleave duplicates deterministically among the burst
    # Guarantee that the original always appears before its duplicate
    burst_stream: List[Dict[str, Any]] = []
    
    # First 30 unique leads go in
    for i in range(30):
        burst_stream.append(unique_leads[i])
    
    # Interleave remaining 40 unique leads and 30 duplicate leads
    dup_idx = 0
    uniq_idx = 30
    toggle = True

    while uniq_idx < 70 or dup_idx < 30:
        if toggle and uniq_idx < 70:
            burst_stream.append(unique_leads[uniq_idx])
            uniq_idx += 1
            if dup_idx < 30:
                toggle = False
        elif not toggle and dup_idx < 30:
            burst_stream.append(duplicate_leads[dup_idx])
            dup_idx += 1
            if uniq_idx < 70:
                toggle = True
        elif uniq_idx < 70:
            burst_stream.append(unique_leads[uniq_idx])
            uniq_idx += 1
        elif dup_idx < 30:
            burst_stream.append(duplicate_leads[dup_idx])
            dup_idx += 1

    return burst_stream


def main() -> None:
    burst = generate_job_burst()
    urls = [job["url"] for job in burst]
    unique_urls = set(urls)

    print(f"Total burst generated: {len(burst)}")
    print(f"Unique URLs: {len(unique_urls)}")
    print(f"Duplicate URLs: {len(burst) - len(unique_urls)}")

    with open("mock_jobs.json", "w", encoding="utf-8") as f:
        json.dump(burst, f, indent=2)
    print("Exported 100 simulated job listings to mock_jobs.json")


if __name__ == "__main__":
    main()
