"""
clean_pipeline.py: High-speed streaming data sanitation pipeline.
Validates raw dirty records against Pydantic schema, stores clean records
into Apache Parquet, and logs quarantined records to JSONL.
Strict constraint: Zero em dashes.
"""

import os
import time
from typing import Dict, Any, Generator, Optional
from decimal import Decimal
from datetime import datetime

try:
    import orjson as json
except ImportError:
    import json

import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import ValidationError

from sanitizer_schema import SanitizedTransaction

# PyArrow schema for output/cleaned_records.parquet
PARQUET_SCHEMA = pa.schema([
    ("record_id", pa.int64()),
    ("client_id", pa.string()),
    ("amount", pa.decimal128(12, 2)),
    ("timestamp", pa.timestamp("us", tz="UTC")),
    ("email", pa.string()),
    ("status", pa.string()),
])

def safe_serialize_json(data: Any) -> bytes:
    """
    Safely serializes quarantine payloads to JSON bytes.
    Coerces raw bytes and non-serializable edge-case objects.
    """
    try:
        res = json.dumps(data)
        return res if isinstance(res, bytes) else res.encode("utf-8")
    except Exception:
        def _default(obj: Any) -> Any:
            if isinstance(obj, (bytes, bytearray)):
                return obj.decode("utf-8", errors="replace")
            return str(obj)
        try:
            res = json.dumps(data, default=_default)
            return res if isinstance(res, bytes) else res.encode("utf-8")
        except Exception:
            fallback = {
                "row_index": data.get("row_index", 0) if isinstance(data, dict) else 0,
                "raw_record": str(data.get("raw_record", data))[:1000] if isinstance(data, dict) else str(data)[:1000],
                "validation_errors": data.get("validation_errors", []) if isinstance(data, dict) else []
            }
            res = json.dumps(fallback, default=str)
            return res if isinstance(res, bytes) else res.encode("utf-8")

def run_pipeline(
    input_source: Any,
    output_parquet_path: str = "output/cleaned_records.parquet",
    output_quarantine_path: str = "output/quarantined_records.jsonl",
    batch_size: int = 10000,
) -> Dict[str, Any]:
    """
    Executes the streaming data sanitization pipeline.
    Accepts a filepath or record generator.
    Guarantees zero uncaught exceptions and exact quarantine error traces.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_parquet_path)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(output_quarantine_path)), exist_ok=True)

    t_start = time.perf_counter()

    valid_count = 0
    quarantine_count = 0
    uncaught_exceptions = 0
    error_type_counts: Dict[str, int] = {}

    batch_columns: Dict[str, list] = {
        "record_id": [],
        "client_id": [],
        "amount": [],
        "timestamp": [],
        "email": [],
        "status": [],
    }

    pq_writer = pq.ParquetWriter(
        output_parquet_path,
        PARQUET_SCHEMA,
        compression="SNAPPY",
        use_dictionary=True
    )

    q_file = open(output_quarantine_path, "wb", buffering=1024 * 1024)
    quarantine_buffer = []

    def flush_valid_batch():
        if batch_columns["record_id"]:
            tbl = pa.Table.from_pydict(batch_columns, schema=PARQUET_SCHEMA)
            pq_writer.write_table(tbl)
            for col in batch_columns:
                batch_columns[col].clear()

    def flush_quarantine_buffer():
        if quarantine_buffer:
            q_file.writelines(quarantine_buffer)
            quarantine_buffer.clear()

    def record_generator() -> Generator[tuple[int, Dict[str, Any]], None, None]:
        if isinstance(input_source, str):
            with open(input_source, "rb") as f:
                for idx, line in enumerate(f):
                    line_stripped = line.strip()
                    if not line_stripped:
                        continue
                    try:
                        yield idx, json.loads(line_stripped)
                    except Exception as parse_err:
                        # Malformed JSON payload quarantined immediately
                        yield idx, {"__raw_corrupt_line__": line.decode("utf-8", errors="replace"), "__parse_error__": str(parse_err)}
        else:
            for idx, item in enumerate(input_source):
                yield idx, item

    for row_idx, raw_record in record_generator():
        try:
            # Check for corrupt raw line case
            if isinstance(raw_record, dict) and "__raw_corrupt_line__" in raw_record:
                quarantine_count += 1
                q_payload = {
                    "row_index": row_idx,
                    "raw_record": raw_record,
                    "validation_errors": [
                        {"loc": ["_json_decoder"], "msg": raw_record.get("__parse_error__", "JSON decode error"), "type": "json_decode_error"}
                    ]
                }
                try:
                    quarantine_buffer.append(json.dumps(q_payload) + b"\n")
                except Exception:
                    quarantine_buffer.append(safe_serialize_json(q_payload) + b"\n")
                if len(quarantine_buffer) >= 5000:
                    flush_quarantine_buffer()
                continue

            # Validate record against Pydantic schema
            model = SanitizedTransaction.model_validate(raw_record)

            batch_columns["record_id"].append(model.record_id)
            batch_columns["client_id"].append(model.client_id)
            batch_columns["amount"].append(model.amount)
            batch_columns["timestamp"].append(model.timestamp)
            batch_columns["email"].append(model.email)
            batch_columns["status"].append(model.status)
            valid_count += 1

            if len(batch_columns["record_id"]) >= batch_size:
                flush_valid_batch()

        except ValidationError as val_err:
            quarantine_count += 1
            err_details = []
            for err in val_err.errors(include_url=False):
                loc_list = [str(x) for x in err.get("loc", ())] or ["_root_"]
                err_type = err.get("type", "validation_error")
                error_type_counts[err_type] = error_type_counts.get(err_type, 0) + 1
                err_details.append({
                    "loc": loc_list,
                    "msg": err.get("msg", "Validation error"),
                    "type": err_type
                })

            q_record = {
                "row_index": row_idx,
                "raw_record": raw_record,
                "validation_errors": err_details
            }
            try:
                quarantine_buffer.append(json.dumps(q_record) + b"\n")
            except Exception:
                quarantine_buffer.append(safe_serialize_json(q_record) + b"\n")

            if len(quarantine_buffer) >= 5000:
                flush_quarantine_buffer()

        except Exception as unexpected_err:
            # Defensive catch: pipeline must maintain zero uncaught crashes
            uncaught_exceptions += 1
            quarantine_count += 1
            q_record = {
                "row_index": row_idx,
                "raw_record": raw_record,
                "validation_errors": [
                    {"loc": ["_unexpected_exception"], "msg": str(unexpected_err), "type": "fatal_runtime_error"}
                ]
            }
            try:
                quarantine_buffer.append(json.dumps(q_record) + b"\n")
            except Exception:
                quarantine_buffer.append(safe_serialize_json(q_record) + b"\n")
            if len(quarantine_buffer) >= 5000:
                flush_quarantine_buffer()

    flush_valid_batch()
    flush_quarantine_buffer()

    pq_writer.close()
    q_file.close()

    t_end = time.perf_counter()
    elapsed_seconds = t_end - t_start
    total_processed = valid_count + quarantine_count
    throughput = total_processed / elapsed_seconds if elapsed_seconds > 0 else 0.0

    return {
        "total_records_processed": total_processed,
        "valid_records_count": valid_count,
        "quarantined_records_count": quarantine_count,
        "uncaught_runtime_exceptions": uncaught_exceptions,
        "execution_time_seconds": round(elapsed_seconds, 4),
        "throughput_records_per_second": round(throughput, 2),
        "error_type_breakdown": error_type_counts,
        "output_parquet_path": output_parquet_path,
        "output_quarantine_path": output_quarantine_path
    }

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run dirty record sanitization pipeline.")
    parser.add_argument("--input", type=str, default="data/dirty_records.jsonl", help="Input JSONL path")
    parser.add_argument("--parquet", type=str, default="output/cleaned_records.parquet", help="Cleaned Parquet path")
    parser.add_argument("--quarantine", type=str, default="output/quarantined_records.jsonl", help="Quarantine JSONL path")
    args = parser.parse_args()

    results = run_pipeline(args.input, args.parquet, args.quarantine)
    print("Pipeline Execution Completed:")
    print(f"Total Processed: {results['total_records_processed']:,}")
    print(f"Valid: {results['valid_records_count']:,}")
    print(f"Quarantined: {results['quarantined_records_count']:,}")
    print(f"Uncaught Exceptions: {results['uncaught_runtime_exceptions']}")
    print(f"Elapsed Time: {results['execution_time_seconds']}s")
    print(f"Throughput: {results['throughput_records_per_second']:,.2f} records/sec")
