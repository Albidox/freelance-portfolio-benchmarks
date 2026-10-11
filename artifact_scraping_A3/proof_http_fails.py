"""
Proof: requests.get() returns empty HTML from quotes.toscrape.com/js/
This demonstrates why browser-based extraction is necessary.
"""
import os
import requests
from bs4 import BeautifulSoup


def run_proof():
    url = "https://quotes.toscrape.com/js/"
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}, timeout=15)
    soup = BeautifulSoup(resp.text, "html.parser")

    # Try to find quotes the same way you would on the non-JS version
    quotes = soup.select("div.quote")
    spans = soup.select("span.text")

    os.makedirs("output", exist_ok=True)
    proof_path = os.path.join("output", "http_failure_proof.txt")
    with open(proof_path, "w", encoding="utf-8") as f:
        f.write("=== HTTP Fetch Proof: quotes.toscrape.com/js/ ===\n\n")
        f.write(f"URL: {url}\n")
        f.write(f"HTTP Status: {resp.status_code}\n")
        f.write(f"Content-Length: {len(resp.text)} bytes\n\n")
        f.write(f"div.quote elements found: {len(quotes)}\n")
        f.write(f"span.text elements found: {len(spans)}\n\n")
        f.write("=== VERDICT ===\n")
        if len(quotes) == 0 and len(spans) == 0:
            f.write("CONFIRMED: requests.get() returns ZERO quotes.\n")
            f.write("The page content is rendered by JavaScript at runtime.\n")
            f.write("Browser-based extraction (Playwright/Camoufox) is REQUIRED.\n\n")
        else:
            f.write(f"UNEXPECTED: Found {len(quotes)} quotes via HTTP. Site may have changed.\n\n")
        f.write("=== First 1000 chars of raw HTML body ===\n")
        f.write(resp.text[:1000])

    print(f"HTTP Status: {resp.status_code}")
    print(f"Quotes found via HTTP: {len(quotes)}")
    print(f"Proof saved to {proof_path}")


if __name__ == "__main__":
    run_proof()
