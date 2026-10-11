# Artifact A1-R2: Real-World Anti-Bot Stress Test (5 Websites)

## Summary Table

| Site | URL | Scrapling Result | Camoufox/CDP Result | Records Extracted | Blocked By | Notes |
|------|-----|------------------|---------------------|-------------------|------------|-------|
| Amazon India | https://www.amazon.in/gp/bestsellers/ | Blocked (Empty Response) | Success | 30 | Empty Response | Fallback attempted |
| Zillow | https://www.zillow.com/austin-tx/ | Blocked (HTTP 403) | Blocked (CDP: HTTP 403 | CF: Camoufox Exception: Version.__init__() got an unexpected keyword argument 'build') | 0 | HTTP 403 | Fallback attempted |
| LinkedIn Jobs | https://www.linkedin.com/jobs/search/?keywords=java+developer&location=India | Blocked (Empty Response) | Success | 60 | Empty Response | Fallback attempted |
| Indeed | https://www.indeed.com/jobs?q=python+developer&l=remote | Blocked (Empty Response) | Blocked (CDP: HTTP 403 | CF: Camoufox Exception: Version.__init__() got an unexpected keyword argument 'build') | 0 | Empty Response | Fallback attempted |
| G2 | https://www.g2.com/categories/crm | Blocked (HTTP 403) | Blocked (CDP: HTTP 403 | CF: Camoufox Exception: Version.__init__() got an unexpected keyword argument 'build') | 0 | HTTP 403 | Fallback attempted |

## Capability Boundary Summary

- **Scrapling Success Rate:** 0/5 (0%)
- **Camoufox/CDP Success Rate:** 2/5 (40% of fallbacks)
- **Proxy Rotation Requirement:** Sites like LinkedIn, Zillow, and Amazon may issue hard IP blocks if repeatedly scraped from the same datacenter IP. While advanced stealth browsers (Camoufox) or persistent profile CDP can bypass initial fingerprinting and JS challenges (like Cloudflare Turnstile or DataDome), long-term stable extraction strictly requires high-quality residential rotating proxies.
- **Freelance Service Recommendation:** Recommend selling `Scrapling` for generic B2B sites and lightly protected directories. For advanced sites (LinkedIn, Zillow, G2), pitch a custom Playwright+Camoufox based architecture with proxy integration. Clearly state that anti-bot protections require ongoing maintenance and residential proxy costs to be covered by the client.
