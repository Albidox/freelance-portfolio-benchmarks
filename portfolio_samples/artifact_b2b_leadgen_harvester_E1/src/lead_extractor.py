"""DOM and regex-based lead extractor with layout-drift heuristics.
Strict zero em dash policy enforced.
"""
import re
from typing import List
from bs4 import BeautifulSoup
from src.models import RawLeadRecord


class LeadExtractor:
    def __init__(self):
        self.error_count: int = 0
        self.quarantine_logged: bool = False
        self.fallback_traversal_active: bool = False

    def extract_from_html(self, html_content: str, source_url: str) -> List[RawLeadRecord]:
        leads: List[RawLeadRecord] = []
        if not html_content or not html_content.strip():
            self.error_count += 1
            self.quarantine_logged = True
            return leads

        soup = BeautifulSoup(html_content, "html.parser")
        cards = soup.select(".company-card")

        # Fallback heuristic if target layout drifted
        if not cards:
            cards = soup.select("div[class*='business'], div[class*='company'], article")
            if cards:
                self.fallback_traversal_active = True

        if not cards:
            # Fallback to pure document regex
            emails = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", html_content)
            for email in emails:
                leads.append(
                    RawLeadRecord(
                        company_name="Extracted Business",
                        source_url=source_url,
                        raw_email=email,
                    )
                )
            return leads

        for card in cards:
            try:
                title_elem = card.select_one("h1, h2, h3, .name, .title")
                company_name = title_elem.get_text(strip=True) if title_elem else "Unknown Company"

                email_elem = card.select_one(".email, a[href^='mailto:']")
                email = None
                if email_elem:
                    email_raw = email_elem.get_text(strip=True) or email_elem.get("href", "")
                    email = email_raw.replace("mailto:", "").split("?")[0].strip()

                phone_elem = card.select_one(".phone, a[href^='tel:']")
                phone = phone_elem.get_text(strip=True) if phone_elem else None

                link_elem = card.select_one("a[href^='http']")
                url = link_elem.get("href") if link_elem else source_url

                leads.append(
                    RawLeadRecord(
                        company_name=company_name,
                        source_url=url,
                        raw_email=email,
                        phone=phone,
                    )
                )
            except Exception:
                self.error_count += 1
                self.quarantine_logged = True

        return leads
