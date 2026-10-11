"""Verification tests for Artifact A1 deliverable files."""
from pathlib import Path
import pyarrow.parquet as pq

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"


def test_csv_line_count_and_header():
    csv_path = OUTPUT_DIR / "books_dataset.csv"
    assert csv_path.exists()
    lines = csv_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1001
    assert lines[0] == "title,price_gbp,rating,in_stock,detail_url,page_number"


def test_parquet_readable_and_count():
    parquet_path = OUTPUT_DIR / "books_dataset.snappy.parquet"
    assert parquet_path.exists()
    table = pq.read_table(parquet_path)
    assert table.num_rows == 1000
    assert table.num_columns == 6
    columns = table.column_names
    assert columns == ["title", "price_gbp", "rating", "in_stock", "detail_url", "page_number"]


def test_run_log_contains_all_pages():
    run_log_path = OUTPUT_DIR / "run_log.txt"
    assert run_log_path.exists()
    content = run_log_path.read_text(encoding="utf-8")
    for i in range(1, 51):
        assert f"Page {i:02d}/50:" in content


def test_sha256sums_format_and_match():
    import hashlib
    sha_path = OUTPUT_DIR / "SHA256SUMS.txt"
    assert sha_path.exists()
    lines = sha_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2

    csv_sha, csv_name = lines[0].split()
    parquet_sha, parquet_name = lines[1].split()

    assert csv_name == "books_dataset.csv"
    assert parquet_name == "books_dataset.snappy.parquet"

    calc_csv = hashlib.sha256((OUTPUT_DIR / "books_dataset.csv").read_bytes()).hexdigest()
    calc_parquet = hashlib.sha256((OUTPUT_DIR / "books_dataset.snappy.parquet").read_bytes()).hexdigest()

    assert csv_sha == calc_csv
    assert parquet_sha == calc_parquet
