"""Mobile User-Agent and TLS JA3/JA4 header fingerprint spoofer bypassing basic Cloudflare Turnstile blocks.
Strict zero em dash policy enforced.
"""
from typing import Dict, Any, Optional, List
from src.models import DevicePlatform, DeviceFingerprint


class HeaderImpersonator:
    """Spoofs browser and mobile client fingerprints to avoid WAF and Turnstile blocks."""

    TURNSTILE_REQUIRED_HINTS = [
        "sec-ch-ua",
        "sec-ch-ua-mobile",
        "sec-ch-ua-platform",
        "sec-fetch-dest",
        "sec-fetch-mode",
        "sec-fetch-site",
    ]

    def __init__(self, default_platform: DevicePlatform = DevicePlatform.ANDROID):
        self.platform = default_platform

    def get_ja3_fingerprint(self, platform: Optional[DevicePlatform] = None) -> str:
        """Return canonical TLS JA3 fingerprint hash for platform."""
        plat = platform or self.platform
        if plat == DevicePlatform.ANDROID:
            return "771,4865-4866-4867-49195-49199-49196-49200-52393-52392,0-23-65281-10-11-35-16-5-13-18-51-45-43-27-17513,29-23-24,0"
        elif plat == DevicePlatform.IOS:
            return "771,49195-49199-49196-49200-52393-52392-49161-49171-49162-49172,0-11-10-35-16-5-13-18-51-45-43-27,29-23-24,0"
        else:
            return "771,4865-4866-4867-49195-49199-49196-49200-52393-52392,0-23-65281-10-11-35-16-5-13-18-51-45-43-27,29-23-24,0"

    def get_ja4_fingerprint(self, platform: Optional[DevicePlatform] = None) -> str:
        """Return modern TLS JA4 fingerprint hash."""
        plat = platform or self.platform
        if plat == DevicePlatform.ANDROID:
            return "t13d1516h2_8daaf6152771_0182476235b2"
        elif plat == DevicePlatform.IOS:
            return "t13d1908h2_9a7d8851412b_1427508215c1"
        else:
            return "t13d1516h2_8daaf6152771_b1248903e1a4"

    def generate_headers(
        self,
        platform: Optional[DevicePlatform] = None,
        target_host: str = "api.target.com",
        bearer_token: Optional[str] = None,
        cf_clearance: Optional[str] = None
    ) -> Dict[str, str]:
        """Generate high-fidelity spoofed headers bypassing Turnstile interstitial challenges."""
        plat = platform or self.platform
        headers: Dict[str, str] = {}

        if plat == DevicePlatform.ANDROID:
            headers = {
                "Host": target_host,
                "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 14; Pixel 8 Pro Build/UQ1A.240205.004)",
                "X-Requested-With": "com.target.android.app",
                "X-Device-Platform": "ANDROID",
                "X-App-Version": "4.28.1",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept": "application/json, text/plain, */*",
                "Connection": "keep-alive",
            }
        elif plat == DevicePlatform.IOS:
            headers = {
                "Host": target_host,
                "User-Agent": "MobileApp/4.28.0 (iPhone; iOS 17.4.1; Scale/3.00)",
                "X-App-Platform": "iOS",
                "X-App-Version": "4.28.0",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept": "application/json",
                "Connection": "keep-alive",
            }
        else:
            # SPA Web with Sec-Ch-Ua client hints to satisfy Cloudflare Turnstile
            headers = {
                "Host": target_host,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-site",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
            }

        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}" if not bearer_token.startswith("Bearer ") else bearer_token
            
        if cf_clearance:
            headers["Cookie"] = f"cf_clearance={cf_clearance}"

        return headers

    def verify_turnstile_compliance(self, headers: Dict[str, str]) -> bool:
        """Verify headers contain required client hints or valid mobile signatures."""
        headers_lower = {k.lower(): v for k, v in headers.items()}
        # Mobile applications bypass Turnstile via native application identifiers
        if "x-device-platform" in headers_lower or "x-requested-with" in headers_lower:
            return True
        # Web clients must supply modern Sec-Ch-Ua hints
        for hint in self.TURNSTILE_REQUIRED_HINTS:
            if hint not in headers_lower:
                return False
        return True
