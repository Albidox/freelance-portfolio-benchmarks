"""
Dataset generator for dirty row stress probe.
Corrupts row 250,000 of the 500,000 row dataset.
Inserts letters into the price column and corrupts the UUID.
Strict zero em dash policy enforced.
"""

import os
import sys

SOURCE_CSV = "inventory_500k.csv"
OUTPUT_DIRTY_CSV = "inventory_500k_dirty.csv"
CORRUPT_ROW_INDEX = 250_000  # 1-indexed data row (line 250,001 including header)


def generate_dirty_dataset(source_path: str = SOURCE_CSV, output_path: str = OUTPUT_DIRTY_CSV):
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Source file not found: {source_path}")

    print(f"Generating corrupted dataset from {source_path} -> {output_path}...")
    corrupted_count = 0
    total_rows = 0

    with open(source_path, "r", encoding="utf-8") as fin, open(output_path, "w", encoding="utf-8", newline="") as fout:
        header = fin.readline()
        fout.write(header)

        for line_num, line in enumerate(fin, start=1):
            total_rows += 1
            if line_num == CORRUPT_ROW_INDEX:
                # Format: id,sku,name,price,stock,category,warehouse_id,created_at
                parts = line.strip().split(",")
                if len(parts) >= 8:
                    parts[0] = "corrupted-uuid-row-250000"
                    parts[3] = "INVALID_PRICE_ABC"
                    corrupted_line = ",".join(parts) + "\n"
                    fout.write(corrupted_line)
                    corrupted_count += 1
                    print(f"Corrupted row {line_num}: {corrupted_line.strip()}")
                else:
                    fout.write(line)
            else:
                fout.write(line)

    print(f"Completed dirty dataset generation. Total rows: {total_rows:,}, Corrupted rows: {corrupted_count}")
    return output_path


if __name__ == "__main__":
    generate_dirty_dataset()
