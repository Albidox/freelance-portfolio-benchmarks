"""Verification test suite for Artifact A3 Round 1 deliverables."""
import os
import hashlib
import pyarrow.parquet as pq
from schema import QuoteRecord


def test_schema_rules():
    print("[Test] Testing QuoteRecord validation rules...")
    # Valid
    q = QuoteRecord(text="The world is a book", author="St. Augustine", tags=["travel", "reading"], page_number=1)
    assert q.text == "The world is a book"
    assert q.author == "St. Augustine"
    assert q.tags == ["travel", "reading"]
    assert q.page_number == 1

    # Unicode quote stripping
    q_unicode = QuoteRecord(text="\u201cHello\u201d", author="X", tags=[], page_number=1)
    assert q_unicode.text == "Hello"

    # Tags as comma-separated string
    q_tags = QuoteRecord(text="Test", author="Y", tags="tag1, tag2", page_number=2)
    assert q_tags.tags == ["tag1", "tag2"]

    # Empty text failure
    try:
        QuoteRecord(text="", author="Test", tags=[], page_number=1)
        assert False, "Should have failed on empty text"
    except Exception:
        pass

    # Empty author failure
    try:
        QuoteRecord(text="Hello", author="", tags=[], page_number=1)
        assert False, "Should have failed on empty author"
    except Exception:
        pass
    print("[Pass] Schema validation tests passed.")


def test_output_artifacts():
    print("[Test] Verifying output artifacts...")
    # 1. http_failure_proof.txt
    proof_path = os.path.join("output", "http_failure_proof.txt")
    assert os.path.exists(proof_path), "http_failure_proof.txt missing"
    with open(proof_path, "r", encoding="utf-8") as f:
        proof_content = f.read()
    assert "CONFIRMED: requests.get() returns ZERO quotes." in proof_content
    assert "div.quote elements found: 0" in proof_content

    # 2. CSV files
    for csv_name in ["quotes_dataset.csv", "quotes_js_dataset.csv"]:
        path = os.path.join("output", csv_name)
        assert os.path.exists(path), f"{csv_name} missing"
        with open(path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        assert len(lines) == 101, f"{csv_name} expected 101 lines, got {len(lines)}"

    # 3. Parquet files
    for pq_name in ["quotes_dataset.snappy.parquet", "quotes_js_dataset.snappy.parquet"]:
        path = os.path.join("output", pq_name)
        assert os.path.exists(path), f"{pq_name} missing"
        table = pq.read_table(path)
        assert table.num_rows == 100, f"{pq_name} expected 100 rows, got {table.num_rows}"

    # 4. Checksums
    sha_path = os.path.join("output", "SHA256SUMS.txt")
    assert os.path.exists(sha_path), "SHA256SUMS.txt missing"
    with open(sha_path, "r", encoding="utf-8") as f:
        sha_lines = [l.strip().split() for l in f if l.strip()]
    for sha, fname in sha_lines:
        fpath = os.path.join("output", fname)
        assert os.path.exists(fpath), f"{fname} referenced in checksums does not exist"
        h = hashlib.sha256(open(fpath, "rb").read()).hexdigest()
        assert h == sha, f"Checksum mismatch for {fname}: computed {h} != recorded {sha}"

    # 5. Run log
    log_path = os.path.join("output", "run_log.txt")
    assert os.path.exists(log_path), "run_log.txt missing"
    with open(log_path, "r", encoding="utf-8") as f:
        log_content = f.read()
    assert "Total valid quotes: 100" in log_content
    assert "Validation failures: 0" in log_content
    assert "Playwright CDP (:9222)" in log_content

    # 6. Real-world probe reports (Round 2)
    for report_name in ["real_world_spa_probe_report.md", "real_world_js_probe_report.md"]:
        report_path = os.path.join("output", report_name)
        assert os.path.exists(report_path), f"{report_name} missing"
        with open(report_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "Target Site Comparison Matrix" in content
        assert "Capability Boundary Summary" in content
        assert "GitHub Trending" in content
        assert "Quotes Infinite Scroll" in content
        assert "Hacker News Algolia" in content

    print("[Pass] All output artifacts verified successfully!")


if __name__ == "__main__":
    test_schema_rules()
    test_output_artifacts()
