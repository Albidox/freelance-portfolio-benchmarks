"""
Database schema initialization for Artifact D12.
Schema: d12_copy_sandbox
Table: inventory
"""

import os
import psycopg2

DB_HOST = os.getenv("PGHOST", "127.0.0.1")
DB_PORT = int(os.getenv("PGPORT", "5433"))
DB_NAME = os.getenv("PGDATABASE", "postgres")
DB_USER = os.getenv("PGUSER", "postgres")
DB_PASSWORD = os.getenv("PGPASSWORD", "")
SCHEMA_NAME = "d12_copy_sandbox"
TABLE_NAME = "inventory"


def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def setup_schema():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME};")
            cur.execute(f"DROP TABLE IF EXISTS {SCHEMA_NAME}.{TABLE_NAME};")
            cur.execute(f"""
                CREATE TABLE {SCHEMA_NAME}.{TABLE_NAME} (
                    id UUID NOT NULL,
                    sku VARCHAR(64) NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    price NUMERIC(10, 2) NOT NULL,
                    stock INTEGER NOT NULL,
                    category VARCHAR(64) NOT NULL,
                    warehouse_id VARCHAR(32) NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                );
            """)
        conn.commit()
        print(f"Successfully created table {SCHEMA_NAME}.{TABLE_NAME}")
    finally:
        conn.close()


if __name__ == "__main__":
    setup_schema()
