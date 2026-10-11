import json
import logging
import time
import concurrent.futures
from bs4 import BeautifulSoup
from scrapling import Fetcher
from playwright.sync_api import sync_playwright
import camoufox
from camoufox.sync_api import Camoufox

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

TARGETS = [
    {
        "name": "Amazon India",
        "url": "https://www.amazon.in/gp/bestsellers/",
        "record_selector": "div.p13n-sc-uncoverable-faceout, #gridItemRoot"
    },
    {
        "name": "Zillow",
        "url": "https://www.zillow.com/austin-tx/",
        "record_selector": "article"
    },
    {
        "name": "LinkedIn Jobs",
        "url": "https://www.linkedin.com/jobs/search/?keywords=java+developer&location=India",
        "record_selector": "ul.jobs-search__results-list > li, .base-card, .job-search-card"
    },
    {
        "name": "Indeed",
        "url": "https://www.indeed.com/jobs?q=python+developer&l=remote",
        "record_selector": "td.resultContent, div.job_seen_beacon, .jobsearch-SerpJobCard"
    },
    {
        "name": "G2",
        "url": "https://www.g2.com/categories/crm",
        "record_selector": ".product-listing, .paper, .product-card"
    }
]

def check_if_blocked(response_text, status_code):
    if status_code in (403, 429, 503):
        return True, f"HTTP {status_code}"
    
    if not response_text:
        return True, "Empty Response"

    soup = BeautifulSoup(response_text, "html.parser")
    title = soup.title.string.lower() if soup.title else ""
    text = soup.get_text().lower()

    if "cloudflare" in text and ("attention required" in text or "challenge" in text or "just a moment" in text or "verify you are human" in text):
        return True, "Cloudflare Challenge"
    if "datadome" in text or "geo.captcha" in text or "captcha" in text:
        return True, "DataDome/Captcha"
    if "verify you are human" in text or "robot" in text or "are you a robot" in text or "security measure" in text:
        return True, "Generic Anti-Bot/Captcha"
    if "access denied" in title or "security measure" in text:
        return True, "Access Denied / WAF"
        
    return False, None

def count_records(html, selector):
    if not html: return 0
    soup = BeautifulSoup(html, "html.parser")
    count = 0
    for sel in selector.split(","):
        sel = sel.strip()
        count = max(count, len(soup.select(sel)))
    return count

def probe_scrapling(url, selector):
    logger.info(f"Probing {url} with Scrapling...")
    try:
        fetcher = Fetcher()
        response = fetcher.get(url)
        status = getattr(response, "status", getattr(response, "status_code", 0))
        is_blocked, reason = check_if_blocked(response.text, status)
        if is_blocked:
            return False, reason, 0
        return True, "Success", count_records(response.text, selector)
    except Exception as e:
        return False, f"Exception: {str(e)}", 0

def run_playwright_cdp(url, selector):
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = context.new_page()
            try:
                response = page.goto(url, timeout=30000, wait_until="domcontentloaded")
                page.wait_for_timeout(5000) # Wait for potential challenges to render
                content = page.content()
                status = response.status if response else 0
                is_blocked, reason = check_if_blocked(content, status)
                
                if is_blocked:
                    return False, reason, 0
                return True, "Success", count_records(content, selector)
            finally:
                page.close()
    except Exception as e:
        return False, f"Playwright Exception: {str(e)}", 0

def probe_playwright_cdp(url, selector):
    logger.info(f"Probing {url} with Playwright CDP...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run_playwright_cdp, url, selector)
        return future.result()

def run_camoufox(url, selector):
    try:
        with Camoufox(headless=True) as browser:
            page = browser.new_page()
            response = page.goto(url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(5000) # Allow JS to execute and WAFs to decide
            content = page.content()
            status = response.status if response else 0
            is_blocked, reason = check_if_blocked(content, status)
            
            if is_blocked:
                return False, reason, 0
            return True, "Success", count_records(content, selector)
    except Exception as e:
        return False, f"Camoufox Exception: {str(e)}", 0

def probe_camoufox(url, selector):
    logger.info(f"Probing {url} with Camoufox...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run_camoufox, url, selector)
        return future.result()


def main():
    results = []
    
    for t in TARGETS:
        site = t["name"]
        url = t["url"]
        sel = t["record_selector"]
        
        scrap_success, scrap_reason, scrap_len = probe_scrapling(url, sel)
        cam_success, cam_reason, cam_len = False, "N/A", 0
        
        if not scrap_success:
            # Fallback to CDP first
            cam_success, cam_reason, cam_len = probe_playwright_cdp(url, sel)
            
            # If CDP fails, let's try Camoufox directly
            if not cam_success:
                cf_success, cf_reason, cf_len = probe_camoufox(url, sel)
                if cf_success:
                    cam_success = True
                    cam_reason = "Success (Camoufox)"
                    cam_len = cf_len
                else:
                    cam_reason = f"CDP: {cam_reason} | CF: {cf_reason}"
        
        results.append({
            "Site": site,
            "URL": url,
            "Scrapling Result": "Success" if scrap_success else f"Blocked ({scrap_reason})",
            "Camoufox/CDP Result": "N/A" if scrap_success else ("Success" if cam_success else f"Blocked ({cam_reason})"),
            "Records Extracted": scrap_len if scrap_success else (cam_len if cam_success else 0),
            "Blocked By": scrap_reason if not scrap_success and not cam_success else ("None" if scrap_success else scrap_reason),
            "Notes": "Fallback attempted" if not scrap_success else "Worked out of box"
        })
        
    print(json.dumps(results, indent=2))

    # Generate markdown report
    import os
    os.makedirs("output", exist_ok=True)
    with open("output/real_world_probe_report.md", "w", encoding="utf-8") as f:
        f.write("# Artifact A1-R2: Real-World Anti-Bot Stress Test (5 Websites)\n\n")
        f.write("## Summary Table\n\n")
        f.write("| Site | URL | Scrapling Result | Camoufox/CDP Result | Records Extracted | Blocked By | Notes |\n")
        f.write("|------|-----|------------------|---------------------|-------------------|------------|-------|\n")
        for r in results:
            f.write(f"| {r['Site']} | {r['URL']} | {r['Scrapling Result']} | {r['Camoufox/CDP Result']} | {r['Records Extracted']} | {r['Blocked By']} | {r['Notes']} |\n")
        
        scrap_succ_cnt = sum(1 for r in results if r['Scrapling Result'] == 'Success')
        cam_succ_cnt = sum(1 for r in results if r['Camoufox/CDP Result'].startswith('Success'))
        total = len(results)
        
        f.write("\n## Capability Boundary Summary\n\n")
        f.write(f"- **Scrapling Success Rate:** {scrap_succ_cnt}/{total} ({(scrap_succ_cnt/total)*100:.0f}%)\n")
        f.write(f"- **Camoufox/CDP Success Rate:** {cam_succ_cnt}/{total - scrap_succ_cnt if total - scrap_succ_cnt > 0 else 1} ({(cam_succ_cnt/max(1, total - scrap_succ_cnt))*100:.0f}% of fallbacks)\n")
        f.write("- **Proxy Rotation Requirement:** Sites like LinkedIn, Zillow, and Amazon may issue hard IP blocks if repeatedly scraped from the same datacenter IP. While advanced stealth browsers (Camoufox) or persistent profile CDP can bypass initial fingerprinting and JS challenges (like Cloudflare Turnstile or DataDome), long-term stable extraction strictly requires high-quality residential rotating proxies.\n")
        f.write("- **Freelance Service Recommendation:** Recommend selling `Scrapling` for generic B2B sites and lightly protected directories. For advanced sites (LinkedIn, Zillow, G2), pitch a custom Playwright+Camoufox based architecture with proxy integration. Clearly state that anti-bot protections require ongoing maintenance and residential proxy costs to be covered by the client.\n")

if __name__ == '__main__':
    main()
