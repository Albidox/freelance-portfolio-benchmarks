"""
Seed orders script for Artifact D11 (PostgreSQL Partial and Composite Index Optimization).
Generates 1,000,000 synthetic orders with skewed status distribution:
5% ACTIVE, 70% COMPLETED, 25% ARCHIVED.
"""

import os
import sys
import time
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


DB_HOST = os.getenv("PGHOST", "127.0.0.1")
DB_PORT = int(os.getenv("PGPORT", "5433"))
DB_NAME = os.getenv("PGDATABASE", "postgres")
DB_USER = os.getenv("PGUSER", "postgres")
DB_PASSWORD = os.getenv("PGPASSWORD", "")
SCHEMA_NAME = "d11_indexing_sandbox"
TABLE_NAME = "orders"
TOTAL_ROWS = 1_000_000


def get_connection(autocommit: bool = False):
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )
    if autocommit:
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    return conn


def init_schema_and_table(conn):
    print(f"Initializing schema '{SCHEMA_NAME}' and table '{TABLE_NAME}'...")
    with conn.cursor() as cur:
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME};")
        cur.execute(f"DROP TABLE IF EXISTS {SCHEMA_NAME}.{TABLE_NAME} CASCADE;")
        cur.execute(f"""
            CREATE TABLE {SCHEMA_NAME}.{TABLE_NAME} (
                order_id BIGSERIAL PRIMARY KEY,
                tenant_id UUID NOT NULL,
                status VARCHAR(32) NOT NULL,
                amount NUMERIC(10, 2) NOT NULL,
                created_at TIMESTAMPTZ NOT NULL,
                metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb
            );
        """)
    conn.commit()
    print("Table created successfully.")


def seed_orders(conn):
    print(f"Seeding {TOTAL_ROWS:,} orders into {SCHEMA_NAME}.{TABLE_NAME}...")
    start_time = time.time()

    seed_sql = f"""
        INSERT INTO {SCHEMA_NAME}.{TABLE_NAME} (tenant_id, status, amount, created_at, metadata)
        SELECT
            gen_random_uuid() AS tenant_id,
            CASE
                WHEN r < 0.05 THEN 'ACTIVE'
                WHEN r < 0.75 THEN 'COMPLETED'
                ELSE 'ARCHIVED'
            END AS status,
            ROUND((random() * 1000 + 10)::numeric, 2) AS amount,
            NOW() - (random() * interval '90 days') AS created_at,
            jsonb_build_object(
                'urgent', (r < 0.05 AND random() < 0.25),
                'region', (ARRAY['us-east', 'us-west', 'eu-central', 'ap-south'])[floor(random() * 4) + 1],
                'items_count', floor(random() * 10) + 1
            ) AS metadata
        FROM (
            SELECT random() AS r
            FROM generate_series(1, %s)
        ) s;
    """

    with conn.cursor() as cur:
        cur.execute(seed_sql, (TOTAL_ROWS,))
    conn.commit()

    duration = time.time() - start_time
    print(f"Inserted {TOTAL_ROWS:,} rows in {duration:.2f} seconds ({TOTAL_ROWS / duration:.0f} rows/sec).")


def analyze_table(conn):
    print(f"Running VACUUM ANALYZE on {SCHEMA_NAME}.{TABLE_NAME}...")
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    start_time = time.time()
    with conn.cursor() as cur:
        cur.execute(f"VACUUM ANALYZE {SCHEMA_NAME}.{TABLE_NAME};")
    duration = time.time() - start_time
    print(f"VACUUM ANALYZE completed in {duration:.2f} seconds.")


def verify_distribution(conn):
    print("Verifying row count and status distribution:")
    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT status, count(*) AS cnt, round(100.0 * count(*) / sum(count(*)) over (), 2) AS pct
            FROM {SCHEMA_NAME}.{TABLE_NAME}
            GROUP BY status
            ORDER BY cnt DESC;
        """)
        rows = cur.fetchall()
        for status, cnt, pct in rows:
            print(f"  Status: {status:<10} Count: {cnt:>8,} ({pct}%)")


def main():
    conn = get_connection()
    try:
        init_schema_and_table(conn)
        seed_orders(conn)
        analyze_table(conn)
        verify_distribution(conn)
    finally:
        conn.close()
    print("Seeding completed successfully.")


if __name__ == "__main__":
    main()
