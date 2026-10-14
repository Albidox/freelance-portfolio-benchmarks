"""Database persistence for ASIN pricing and Buy Box history in PostgreSQL 18."""

import psycopg2
from typing import List, Dict, Any, Optional, Tuple
from src.config import SPAPIConfig
from src.models import ASINRecord, BuyBoxSnapshot, RepricingDecision


class MarketplaceStore:
    """Manages transactional persistence of ASIN tracking and Buy Box states."""

    def __init__(self, config: SPAPIConfig):
        self.config = config

    def get_connection(self):
        """Connect to Native PostgreSQL 18 on port 5433."""
        return psycopg2.connect(
            host=self.config.db_host,
            port=self.config.db_port,
            user=self.config.db_user,
            password=self.config.db_password,
            dbname=self.config.db_name,
            options=f"-c search_path={self.config.db_schema},public",
        )

    def initialize_schema(self) -> None:
        """Create schema and tables in PostgreSQL 18."""
        ddl = f"""
        CREATE SCHEMA IF NOT EXISTS {self.config.db_schema};
        SET search_path TO {self.config.db_schema};

        CREATE TABLE IF NOT EXISTS tracked_asins (
            asin VARCHAR(32) PRIMARY KEY,
            marketplace_id VARCHAR(32) NOT NULL,
            title VARCHAR(512),
            floor_price NUMERIC(10, 2) NOT NULL,
            ceiling_price NUMERIC(10, 2) NOT NULL,
            current_our_price NUMERIC(10, 2) NOT NULL,
            target_margin_percent NUMERIC(5, 2) DEFAULT 15.0,
            is_active BOOLEAN DEFAULT TRUE,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS buybox_snapshots (
            id SERIAL PRIMARY KEY,
            asin VARCHAR(32) REFERENCES tracked_asins(asin),
            marketplace_id VARCHAR(32) NOT NULL,
            has_buybox_winner BOOLEAN NOT NULL,
            is_our_seller_winner BOOLEAN NOT NULL,
            winner_seller_id VARCHAR(64),
            winner_landed_price NUMERIC(10, 2),
            total_competitive_offers INT,
            is_suppressed BOOLEAN NOT NULL,
            captured_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS repricing_decisions (
            id SERIAL PRIMARY KEY,
            asin VARCHAR(32) REFERENCES tracked_asins(asin),
            current_price NUMERIC(10, 2) NOT NULL,
            recommended_price NUMERIC(10, 2) NOT NULL,
            rule_name VARCHAR(64) NOT NULL,
            floor_enforced BOOLEAN NOT NULL,
            ceiling_enforced BOOLEAN NOT NULL,
            price_delta NUMERIC(10, 2) NOT NULL,
            decided_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_snapshots_asin ON buybox_snapshots(asin, captured_at DESC);
        CREATE INDEX IF NOT EXISTS idx_decisions_asin ON repricing_decisions(asin, decided_at DESC);
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(ddl)
            conn.commit()

    def upsert_tracked_asin(self, record: ASINRecord) -> bool:
        """Upsert a tracked ASIN catalog record."""
        sql = f"""
        INSERT INTO {self.config.db_schema}.tracked_asins
        (asin, marketplace_id, title, floor_price, ceiling_price, current_our_price, target_margin_percent, is_active, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (asin) DO UPDATE SET
            floor_price = EXCLUDED.floor_price,
            ceiling_price = EXCLUDED.ceiling_price,
            current_our_price = EXCLUDED.current_our_price,
            updated_at = CURRENT_TIMESTAMP;
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        record.asin,
                        record.marketplace_id,
                        record.title,
                        float(record.floor_price),
                        float(record.ceiling_price),
                        float(record.current_our_price),
                        record.target_margin_percent,
                        record.is_active,
                    ),
                )
            conn.commit()
        return True

    def record_snapshot_and_decision(
        self, snapshot: BuyBoxSnapshot, decision: RepricingDecision
    ) -> bool:
        """Transactionally record Buy Box snapshot and repricing action."""
        sql_snap = f"""
        INSERT INTO {self.config.db_schema}.buybox_snapshots
        (asin, marketplace_id, has_buybox_winner, is_our_seller_winner, winner_seller_id, winner_landed_price, total_competitive_offers, is_suppressed)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
        """
        sql_dec = f"""
        INSERT INTO {self.config.db_schema}.repricing_decisions
        (asin, current_price, recommended_price, rule_name, floor_enforced, ceiling_enforced, price_delta)
        VALUES (%s, %s, %s, %s, %s, %s, %s);
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql_snap,
                    (
                        snapshot.asin,
                        snapshot.marketplace_id,
                        snapshot.has_buybox_winner,
                        snapshot.is_our_seller_winner,
                        snapshot.winner_seller_id,
                        float(snapshot.winner_landed_price) if snapshot.winner_landed_price is not None else None,
                        snapshot.total_competitive_offers,
                        snapshot.is_suppressed,
                    ),
                )
                cur.execute(
                    sql_dec,
                    (
                        decision.asin,
                        float(decision.current_price),
                        float(decision.recommended_price),
                        decision.rule_name,
                        decision.floor_enforced,
                        decision.ceiling_enforced,
                        float(decision.price_delta),
                    ),
                )
            conn.commit()
        return True

    def batch_record_snapshots(
        self, items: List[Tuple[BuyBoxSnapshot, RepricingDecision]]
    ) -> int:
        """Batch insert snapshots and decisions within a single transaction."""
        sql_snap = f"""
        INSERT INTO {self.config.db_schema}.buybox_snapshots
        (asin, marketplace_id, has_buybox_winner, is_our_seller_winner, winner_seller_id, winner_landed_price, total_competitive_offers, is_suppressed)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
        """
        sql_dec = f"""
        INSERT INTO {self.config.db_schema}.repricing_decisions
        (asin, current_price, recommended_price, rule_name, floor_enforced, ceiling_enforced, price_delta)
        VALUES (%s, %s, %s, %s, %s, %s, %s);
        """
        snap_rows = [
            (
                s.asin,
                s.marketplace_id,
                s.has_buybox_winner,
                s.is_our_seller_winner,
                s.winner_seller_id,
                float(s.winner_landed_price) if s.winner_landed_price is not None else None,
                s.total_competitive_offers,
                s.is_suppressed,
            )
            for s, _ in items
        ]
        dec_rows = [
            (
                d.asin,
                float(d.current_price),
                float(d.recommended_price),
                d.rule_name,
                d.floor_enforced,
                d.ceiling_enforced,
                float(d.price_delta),
            )
            for _, d in items
        ]

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(sql_snap, snap_rows)
                cur.executemany(sql_dec, dec_rows)
            conn.commit()
        return len(items)
