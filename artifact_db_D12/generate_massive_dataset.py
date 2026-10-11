"""
Dataset generation script for Artifact D12.
Generates 500,000 realistic inventory records in CSV format.
Strict zero em dash policy enforced.
"""

import os
import time
import random

CSV_FILENAME = "inventory_500k.csv"
TOTAL_ROWS = 500_000
CHUNK_SIZE = 10_000

CATEGORIES = [
    "Electronics", "Hardware", "Industrial Tools", "Fasteners",
    "Pneumatics", "Safety Equipment", "Hydraulics", "Material Handling"
]

WAREHOUSES = [
    "WH-EAST-01", "WH-EAST-02", "WH-WEST-01", "WH-WEST-02",
    "WH-NORTH-01", "WH-SOUTH-01", "WH-CENTRAL-01"
]

ADJECTIVES = ["Heavy-Duty", "Precision", "Industrial", "Modular", "High-Torque", "Compact", "Titanium", "Reinforced"]
NOUNS = ["Bearing", "Flange", "Coupler", "Actuator", "Sensor", "Valve", "Bracket", "Gear", "Piston", "Drive"]


def generate_dataset(output_path: str = CSV_FILENAME, total_rows: int = TOTAL_ROWS) -> str:
    print(f"Generating {total_rows:,} inventory rows to {output_path}...")
    start_time = time.perf_counter()
    rng = random.Random(42)

    categories_len = len(CATEGORIES)
    warehouses_len = len(WAREHOUSES)
    adj_len = len(ADJECTIVES)
    noun_len = len(NOUNS)

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        # Header matching database columns
        f.write("id,sku,name,price,stock,category,warehouse_id,created_at\n")

        lines = []
        for i in range(1, total_rows + 1):
            # Deterministic, standard UUIDv4 format
            row_id = f"00000000-0000-4000-8000-{i:012x}"
            cat_idx = rng.randrange(categories_len)
            category = CATEGORIES[cat_idx]
            warehouse = WAREHOUSES[rng.randrange(warehouses_len)]
            item_name = f"{ADJECTIVES[rng.randrange(adj_len)]} {NOUNS[rng.randrange(noun_len)]} Mod-{i % 997}"
            sku = f"SKU-{cat_idx:02d}-{i:07d}"
            price = f"{(rng.randint(100, 99990) / 100.0):.2f}"
            stock = rng.randint(0, 5000)
            # Deterministic ISO timestamp
            day = 1 + (i % 28)
            month = 1 + ((i // 28) % 12)
            created_at = f"2026-{month:02d}-{day:02d}T10:00:00Z"

            lines.append(f"{row_id},{sku},{item_name},{price},{stock},{category},{warehouse},{created_at}\n")

            if i % CHUNK_SIZE == 0:
                f.writelines(lines)
                lines.clear()

        if lines:
            f.writelines(lines)
            lines.clear()

    elapsed = time.perf_counter() - start_time
    file_size_bytes = os.path.getsize(output_path)
    file_size_mb = file_size_bytes / (1024 * 1024)
    print(f"Generated {total_rows:,} rows in {elapsed:.2f} seconds ({file_size_mb:.2f} MB).")
    return output_path


if __name__ == "__main__":
    generate_dataset()
