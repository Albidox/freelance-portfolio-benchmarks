"""
generate_dirty_data.py: Synthetic dirty dataset generator.
Generates 100,000 records with realistic client data errors and multi-format strings.
Strict constraint: Zero em dashes.
"""

import os
import json
import random
import argparse
from typing import Generator, Dict, Any

RANDOM_SEED = 42

VALID_CURRENCIES = [
    "$19.99", "$49.50", "19.99 USD", "99.00 USD", "€45.50", "£12.00",
    " $ 1,499.99 ", "FREE", "0.00", "125.75", "€ 890.00", "$ 9.95",
    "350.00 EUR", "75.20 GBP", "$0.99", "5000.00"
]

DIRTY_CURRENCIES = [
    "-5.00", "-$25.50", "-150.00 USD", "NaN", "N/A", "undefined",
    "invalid_price", None, "ERROR_VAL", "--10.00"
]

VALID_DATES = [
    "2026-10-10", "2026-10-10T14:30:00Z", "10/10/2026", "05/12/2026",
    "2026/10/10", "2026-10-10 09:15:30", "2026-01-15T00:00:00",
    "12/31/2025", "2026-08-20"
]

DIRTY_DATES = [
    "yesterday", "invalid_date", "99/99/9999", "tomorrow", "null",
    None, "2026-02-31", "NOT_A_DATE", "9999-99-99"
]

VALID_EMAILS = [
    "user@example.com", "finance.ops@company.org", "lead.engineer@startup.io",
    "auditor@compliance.gov", "dev_team@fintech.net", "billing@saas.com",
    "customer.support@enterprise.co.uk", "admin@domain.systems"
]

DIRTY_EMAILS = [
    "missing_at_symbol", "null", "@nodomain.com", "user@",
    "spaces in email@domain.com", None, "broken@@domain.com",
    "invalid.domain..com", "no_domain_at_all"
]

STATUSES = ["active", "completed", "pending", "settled", "flagged"]

def create_record(record_id: int, rng: random.Random) -> Dict[str, Any]:
    client_id = f"CL-{1000 + (record_id % 2500):04d}"
    status = rng.choice(STATUSES)

    # 85% clean/sanitizable, 15% quarantine candidates
    is_dirty = (rng.random() < 0.15)
    if not is_dirty:
        return {
            "record_id": record_id,
            "client_id": client_id,
            "amount": rng.choice(VALID_CURRENCIES),
            "timestamp": rng.choice(VALID_DATES),
            "email": rng.choice(VALID_EMAILS),
            "status": status
        }

    # Inject specific dirty bug type
    bug_type = rng.choice(["currency", "date", "email", "compound"])
    if bug_type == "currency":
        amount = rng.choice(DIRTY_CURRENCIES)
        timestamp = rng.choice(VALID_DATES)
        email = rng.choice(VALID_EMAILS)
    elif bug_type == "date":
        amount = rng.choice(VALID_CURRENCIES)
        timestamp = rng.choice(DIRTY_DATES)
        email = rng.choice(VALID_EMAILS)
    elif bug_type == "email":
        amount = rng.choice(VALID_CURRENCIES)
        timestamp = rng.choice(VALID_DATES)
        email = rng.choice(DIRTY_EMAILS)
    else:
        # Compound error
        amount = rng.choice(DIRTY_CURRENCIES)
        timestamp = rng.choice(DIRTY_DATES)
        email = rng.choice(DIRTY_EMAILS)

    return {
        "record_id": record_id,
        "client_id": client_id,
        "amount": amount,
        "timestamp": timestamp,
        "email": email,
        "status": status
    }

def stream_dirty_records(count: int = 100000, seed: int = RANDOM_SEED) -> Generator[Dict[str, Any], None, None]:
    rng = random.Random(seed)
    for i in range(count):
        yield create_record(i, rng)

def generate_dirty_dataset(output_path: str, count: int = 100000, seed: int = RANDOM_SEED) -> int:
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    rng = random.Random(seed)
    written = 0
    buffer = []

    with open(output_path, "w", encoding="utf-8", buffering=1024 * 1024) as f:
        for i in range(count):
            rec = create_record(i, rng)
            buffer.append(json.dumps(rec) + "\n")
            written += 1
            if len(buffer) >= 10000:
                f.writelines(buffer)
                buffer.clear()
        if buffer:
            f.writelines(buffer)
            buffer.clear()

    return written

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic dirty dataset.")
    parser.add_argument("--count", type=int, default=100000, help="Total records to generate")
    parser.add_argument("--output", type=str, default="data/dirty_records.jsonl", help="Output path")
    parser.add_argument("--seed", type=int, default=RANDOM_SEED, help="Random seed")
    args = parser.parse_args()

    print(f"Generating {args.count} records to {args.output} with seed={args.seed}...")
    total = generate_dirty_dataset(args.output, args.count, args.seed)
    print(f"Successfully generated {total} records.")
