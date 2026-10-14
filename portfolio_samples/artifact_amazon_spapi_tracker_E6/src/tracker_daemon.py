"""Scheduled polling loop tracking competitor ASIN price updates with SQLite WAL delta state storage."""

import sqlite3
import time
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple
from src.config import SPAPIConfig
from src.models import ASINRecord, BuyBoxSnapshot, RepricingDecision
from src.asin_tracker import ASINTracker
from src.buybox_monitor import BuyBoxMonitor
from src.marketplace_store import MarketplaceStore


class TrackerDaemon:
    """Continuous polling and delta synchronization engine with SQLite WAL local buffer."""

    def __init__(
        self,
        config: SPAPIConfig,
        sqlite_db_path: Optional[str] = None,
        our_seller_id: str = "A3OURSELLERID",
    ):
        self.config = config
        self.sqlite_db_path = sqlite_db_path or config.sqlite_cache_path
        self.tracker = ASINTracker(our_seller_id=our_seller_id)
        self.monitor = BuyBoxMonitor()
        self.store = MarketplaceStore(config)
        self.cycles_executed: int = 0
        self.deltas_recorded: int = 0
        self._init_sqlite_wal()

    def _get_sqlite_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.sqlite_db_path, timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_sqlite_wal(self) -> None:
        """Initialize local SQLite WAL database for delta tracking."""
        with self._get_sqlite_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS asin_deltas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asin TEXT NOT NULL,
                    old_price REAL NOT NULL,
                    new_price REAL NOT NULL,
                    price_delta REAL NOT NULL,
                    has_buybox_winner INTEGER NOT NULL,
                    is_our_winner INTEGER NOT NULL,
                    winner_seller_id TEXT,
                    winner_price REAL,
                    rule_name TEXT NOT NULL,
                    captured_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_deltas_asin ON asin_deltas(asin, captured_at DESC);"
            )
            conn.commit()

    def record_delta(
        self,
        asin: str,
        old_price: Decimal,
        decision: RepricingDecision,
        snapshot: BuyBoxSnapshot,
    ) -> None:
        """Persist price and winner delta into SQLite WAL cache."""
        with self._get_sqlite_connection() as conn:
            conn.execute(
                """
                INSERT INTO asin_deltas
                (asin, old_price, new_price, price_delta, has_buybox_winner, is_our_winner, winner_seller_id, winner_price, rule_name, captured_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    asin,
                    float(old_price),
                    float(decision.recommended_price),
                    float(decision.price_delta),
                    1 if snapshot.has_buybox_winner else 0,
                    1 if snapshot.is_our_seller_winner else 0,
                    snapshot.winner_seller_id,
                    float(snapshot.winner_landed_price) if snapshot.winner_landed_price is not None else None,
                    decision.rule_name,
                    decision.decided_at,
                ),
            )
            conn.commit()
        self.deltas_recorded += 1

    def batch_record_deltas(
        self,
        deltas: List[Tuple[str, Decimal, RepricingDecision, BuyBoxSnapshot]],
    ) -> int:
        """Batch persist price and winner deltas into SQLite WAL cache in a single transaction."""
        rows = [
            (
                asin,
                float(old_price),
                float(decision.recommended_price),
                float(decision.price_delta),
                1 if snapshot.has_buybox_winner else 0,
                1 if snapshot.is_our_seller_winner else 0,
                snapshot.winner_seller_id,
                float(snapshot.winner_landed_price) if snapshot.winner_landed_price is not None else None,
                decision.rule_name,
                decision.decided_at,
            )
            for asin, old_price, decision, snapshot in deltas
        ]
        with self._get_sqlite_connection() as conn:
            conn.executemany(
                """
                INSERT INTO asin_deltas
                (asin, old_price, new_price, price_delta, has_buybox_winner, is_our_winner, winner_seller_id, winner_price, rule_name, captured_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                rows,
            )
            conn.commit()
        self.deltas_recorded += len(rows)
        return len(rows)

    def process_asin_payload(
        self,
        asin_record: ASINRecord,
        pricing_payload: Dict[str, Any],
        persist_to_postgres: bool = False,
    ) -> Tuple[BuyBoxSnapshot, RepricingDecision]:
        """Parse pricing payload, calculate repricing action, and log deltas."""
        snapshot = self.tracker.parse_competitive_pricing(
            asin=asin_record.asin,
            marketplace_id=asin_record.marketplace_id,
            payload=pricing_payload,
        )
        decision = self.monitor.compute_repricing(asin_record, snapshot)

        # Record delta if recommended price differs or winner updated
        if decision.price_delta != Decimal("0.00") or not snapshot.is_our_seller_winner:
            self.record_delta(asin_record.asin, asin_record.current_our_price, decision, snapshot)

        if persist_to_postgres:
            self.store.record_snapshot_and_decision(snapshot, decision)

        return snapshot, decision
