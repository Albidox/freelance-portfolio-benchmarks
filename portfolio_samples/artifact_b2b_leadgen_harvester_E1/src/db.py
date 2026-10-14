"""Dynamic PostgreSQL 18 schema loader (sandbox_e1) on port 5433 with deduplication.
Strict zero em dash policy enforced.
"""
import asyncio
import logging
import psycopg2
from psycopg2.extras import execute_values
from typing import List, Optional
from src.config import HarvesterConfig
from src.models import RawLeadRecord, VerifiedLead
from src.crawler import B2BDirectoryCrawler
from src.lead_extractor import LeadExtractor
from src.validator import EmailVerifier

logger = logging.getLogger("db_orchestrator")


class DatabaseManager:
    def __init__(self, config: Optional[HarvesterConfig] = None):
        self.config = config or HarvesterConfig()

    def get_connection(self):
        return psycopg2.connect(
            host=self.config.db_host,
            port=self.config.db_port,
            user=self.config.db_user,
            password=self.config.db_password,
            dbname=self.config.db_name,
            connect_timeout=10,
        )

    def init_database(self):
        """Initializes PostgreSQL 18 dynamic schema and tables on port 5433."""
        conn = self.get_connection()
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {self.config.db_schema};")
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.config.db_schema}.b2b_leads (
                    id SERIAL PRIMARY KEY,
                    company_name TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    is_deliverable BOOLEAN NOT NULL,
                    mx_records TEXT[],
                    smtp_check_passed BOOLEAN NOT NULL,
                    phone TEXT,
                    address TEXT,
                    contact_name TEXT,
                    industry TEXT,
                    source_url TEXT,
                    confidence_score REAL,
                    verification_latency_ms REAL,
                    verified_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_b2b_leads_domain ON {self.config.db_schema}.b2b_leads(domain);
                CREATE INDEX IF NOT EXISTS idx_b2b_leads_deliverable ON {self.config.db_schema}.b2b_leads(is_deliverable);
            """
            )
        conn.close()

    def persist_batch(self, leads: List[VerifiedLead]) -> int:
        if not leads:
            return 0
        conn = self.get_connection()
        query = f"""
            INSERT INTO {self.config.db_schema}.b2b_leads (
                company_name, domain, email, is_deliverable, mx_records,
                smtp_check_passed, phone, address, contact_name, industry,
                source_url, confidence_score, verification_latency_ms
            ) VALUES %s
            ON CONFLICT (email) DO UPDATE SET
                is_deliverable = EXCLUDED.is_deliverable,
                confidence_score = EXCLUDED.confidence_score,
                verification_latency_ms = EXCLUDED.verification_latency_ms;
        """
        # Deduplicate within batch by email to prevent CardinalityViolation
        unique_map = {}
        for lead in leads:
            if lead and lead.email:
                unique_map[lead.email.strip().lower()] = lead
        deduped_leads = list(unique_map.values())

        records = [
            (
                lead.company_name,
                lead.domain,
                lead.email,
                lead.is_deliverable,
                lead.mx_records,
                lead.smtp_check_passed,
                lead.phone,
                lead.address,
                lead.contact_name,
                lead.industry,
                lead.source_url,
                lead.confidence_score,
                lead.verification_latency_ms,
            )
            for lead in deduped_leads
        ]
        with conn.cursor() as cur:
            execute_values(cur, query, records)
        conn.commit()
        conn.close()
        return len(deduped_leads)


class PipelineOrchestrator:
    def __init__(self, config: Optional[HarvesterConfig] = None):
        self.config = config or HarvesterConfig()
        self.db = DatabaseManager(self.config)
        self.crawler = B2BDirectoryCrawler(
            concurrency=self.config.max_concurrency,
            timeout=self.config.request_timeout_seconds,
            rate_limit_per_second=self.config.rate_limit_per_second,
        )
        self.extractor = LeadExtractor()
        self.verifier = EmailVerifier(config=self.config)
        self.total_inserted: int = 0

    def init_database(self):
        self.db.init_database()

    def persist_batch(self, leads: List[VerifiedLead]) -> int:
        count = self.db.persist_batch(leads)
        self.total_inserted += count
        return count

    async def run_pipeline(self, target_urls: List[str]) -> List[VerifiedLead]:
        raw_pages = await self.crawler.crawl_directory(target_urls)
        all_raw_leads: List[RawLeadRecord] = []
        for idx, page in enumerate(raw_pages):
            url = target_urls[idx] if idx < len(target_urls) else "https://directory.internal"
            all_raw_leads.extend(self.extractor.extract_from_html(page, url))

        verification_tasks = [self.verifier.verify_lead(lead) for lead in all_raw_leads]
        verified_results = await asyncio.gather(*verification_tasks)
        valid_leads = [lead for lead in verified_results if lead is not None]

        return valid_leads
