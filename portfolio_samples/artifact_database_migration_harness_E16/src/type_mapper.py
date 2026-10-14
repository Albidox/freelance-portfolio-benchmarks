"""Dynamic cross-database schema and type translation engine (MySQL/Mongo to PostgreSQL 18).
Strict zero em dash policy enforced.
"""
from typing import Dict, Any, List, Optional, Tuple
from src.models import TargetDataType, ColumnMapping
from src.schema_transformer import SchemaTransformer


class TypeMapper:
    """Dynamic cross-database schema and type translation engine."""

    def __init__(self, quarantine_invalid: bool = True):
        self.transformer = SchemaTransformer(quarantine_invalid=quarantine_invalid)

    def map_mysql_type_to_postgres(self, mysql_type: str) -> TargetDataType:
        """Translates MySQL data type definition to PostgreSQL 18 TargetDataType."""
        return self.transformer.transform_mysql_datatype(mysql_type)

    def infer_postgres_type_from_value(self, value: Any) -> TargetDataType:
        """Infers PostgreSQL 18 type from a runtime value."""
        if value is None:
            return TargetDataType.VARCHAR
        if isinstance(value, bool):
            return TargetDataType.BOOLEAN
        if isinstance(value, int):
            if value > 2147483647 or value < -2147483648:
                return TargetDataType.BIGINT
            return TargetDataType.INTEGER
        if isinstance(value, float):
            return TargetDataType.NUMERIC
        if isinstance(value, (dict, list)):
            return TargetDataType.JSONB
        str_val = str(value)
        if len(str_val) > 255:
            return TargetDataType.TEXT
        return TargetDataType.VARCHAR

    def build_schema_mapping(self, table_schema: Dict[str, str]) -> Dict[str, ColumnMapping]:
        """Builds ColumnMapping dictionary from table schema definition."""
        mappings: Dict[str, ColumnMapping] = {}
        for col_name, col_type in table_schema.items():
            pg_type = self.map_mysql_type_to_postgres(col_type)
            is_pk = (col_name.lower() in ("id", "pk", f"{col_name}_id"))
            mappings[col_name] = ColumnMapping(
                source_field=col_name,
                target_column=col_name.lower(),
                target_type=pg_type,
                is_primary_key=is_pk,
                is_nullable=not is_pk
            )
        return mappings

    def infer_schema_from_documents(self, documents: List[Dict[str, Any]]) -> Dict[str, TargetDataType]:
        """Infers target PostgreSQL 18 column types from a list of documents."""
        schema: Dict[str, TargetDataType] = {}
        for doc in documents:
            for k, v in doc.items():
                if k == "_id":
                    schema["id"] = TargetDataType.VARCHAR
                    continue
                current_type = schema.get(k)
                inferred_type = self.infer_postgres_type_from_value(v)
                if current_type is None:
                    schema[k] = inferred_type
                elif current_type != inferred_type:
                    # Upgrade to JSONB or TEXT if polymorphic types detected
                    if current_type == TargetDataType.JSONB or inferred_type == TargetDataType.JSONB:
                        schema[k] = TargetDataType.JSONB
                    else:
                        schema[k] = TargetDataType.TEXT
        return schema

    def generate_postgres_ddl(
        self,
        schema_name: str,
        table_name: str,
        columns: Dict[str, TargetDataType]
    ) -> str:
        """Generates PostgreSQL 18 table creation DDL."""
        col_defs = []
        for col_name, col_type in columns.items():
            if col_name == "id":
                col_defs.append(f'"{col_name}" VARCHAR(128) PRIMARY KEY')
            else:
                col_defs.append(f'\"{col_name}\" {col_type.value}')
        inner = ", ".join(col_defs)
        return f'CREATE TABLE IF NOT EXISTS "{schema_name}"."{table_name}" ({inner});'
