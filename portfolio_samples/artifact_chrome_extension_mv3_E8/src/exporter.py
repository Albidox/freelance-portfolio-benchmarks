"""RFC 4180 compliant CSV stream builder, column mapper, and JSON generator."""
import io
import json
from typing import List, Dict, Any, Optional
from src.models import ColumnMapping, ExportFormat


class DataExporter:
    @staticmethod
    def escape_csv_field(value: str) -> str:
        """Escape field per RFC 4180 standards: wrap in quotes if contains comma, quote, or newline."""
        if value is None:
            return '""'
        s = str(value)
        needs_quoting = ("," in s) or ('"' in s) or (chr(10) in s) or (chr(13) in s)
        if needs_quoting:
            escaped = s.replace('"', '""')
            return f'"{escaped}"'
        return s

    def export_csv_stream(self, records: List[Dict[str, Any]], column_mappings: Optional[List[ColumnMapping]] = None) -> str:
        """Generate complete RFC 4180 CSV text with custom column mapping."""
        if not records:
            return ""

        # Determine target columns
        if column_mappings:
            headers = [m.target_column for m in column_mappings]
            keys = [m.source_field for m in column_mappings]
        else:
            keys = list(records[0].keys())
            headers = keys

        output = io.StringIO()
        # Write headers
        output.write(",".join(self.escape_csv_field(h) for h in headers) + chr(13) + chr(10))

        # Write data rows
        for rec in records:
            row_vals = []
            for k in keys:
                val = rec.get(k, "")
                row_vals.append(self.escape_csv_field(val))
            output.write(",".join(row_vals) + chr(13) + chr(10))

        return output.getvalue()

    def export_json(self, records: List[Dict[str, Any]], pretty: bool = False) -> str:
        """Generate structured JSON array output."""
        indent = 2 if pretty else None
        return json.dumps(records, indent=indent, ensure_ascii=False)

    def chunk_records(self, records: List[Dict[str, Any]], chunk_size: int = 2000) -> List[List[Dict[str, Any]]]:
        """Partition large record sets into chunks to prevent browser memory exhaustion."""
        return [records[i:i + chunk_size] for i in range(0, len(records), chunk_size)]
