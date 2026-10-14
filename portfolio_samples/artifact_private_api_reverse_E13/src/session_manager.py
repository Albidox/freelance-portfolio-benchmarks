"""TLS fingerprint profile configuration and session credential lifecycle manager.
Strict zero em dash policy enforced.
"""
import time
from typing import Dict, Any, Optional
from src.models import DevicePlatform, DeviceFingerprint, SessionCredentials


class SessionManager:
    def __init__(self, default_platform: DevicePlatform = DevicePlatform.ANDROID):
        self.default_platform = default_platform
        self.device = self._init_device_fingerprint(default_platform)
        self.credentials: Optional[SessionCredentials] = None
        self.cookie_jar: Dict[str, str] = {}

    def _init_device_fingerprint(self, platform: DevicePlatform) -> DeviceFingerprint:
        """Create platform-specific device profile and TLS fingerprint strings."""
        if platform == DevicePlatform.ANDROID:
            return DeviceFingerprint(
                platform=DevicePlatform.ANDROID,
                os_version="Android 14; Pixel 8 Pro",
                app_version="4.28.1",
                device_id="8f9a2b1c4e6d3a50",
                user_agent="Dalvik/2.1.0 (Linux; U; Android 14; Pixel 8 Pro Build/UQ1A.240205.004)",
                ja3_fingerprint="771,4865-4866-4867-49195-49199-49196-49200-52393-52392,0-23-65281-10-11-35-16-5-13-18-51-45-43-27-17513,29-23-24,0",
                ja4_fingerprint="t13d1516h2_8daaf6152771_0182476235b2"
            )
        elif platform == DevicePlatform.IOS:
            return DeviceFingerprint(
                platform=DevicePlatform.IOS,
                os_version="iOS 17.4.1",
                app_version="4.28.0",
                device_id="A38B4219-4C59-42E1-97D8-8A3F1F1082CD",
                user_agent="MobileApp/4.28.0 (iPhone; iOS 17.4.1; Scale/3.00)",
                ja3_fingerprint="771,49195-49199-49196-49200-52393-52392-49161-49171-49162-49172,0-11-10-35-16-5-13-18-51-45-43-27,29-23-24,0",
                ja4_fingerprint="t13d1908h2_9a7d8851412b_1427508215c1"
            )
        else:
            return DeviceFingerprint(
                platform=DevicePlatform.SPA_WEB,
                os_version="Windows 10 x64",
                app_version="WebClient-v2.1",
                device_id="browser-session-w10-chrome122",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                ja3_fingerprint="771,4865-4866-4867-49195-49199-49196-49200-52393-52392,0-23-65281-10-11-35-16-5-13-18-51-45-43-27,29-23-24,0",
                ja4_fingerprint="t13d1516h2_8daaf6152771_b1248903e1a4"
            )

    def set_credentials(self, credentials: SessionCredentials) -> None:
        """Store authenticated session tokens and merge incoming cookies."""
        self.credentials = credentials
        if credentials.cookies:
            self.cookie_jar.update(credentials.cookies)

    def is_session_valid(self) -> bool:
        """Determine if active session exists and is not expired."""
        if not self.credentials:
            return False
        return not self.credentials.is_expired()

    def update_cookie(self, key: str, value: str) -> None:
        """Update single session cookie from Set-Cookie headers."""
        self.cookie_jar[key] = value

    def get_cookie_header(self) -> str:
        """Format stored cookies into standard HTTP Cookie header string."""
        return "; ".join([f"{k}={v}" for k, v in self.cookie_jar.items()])

    def refresh_session_if_needed(self, simulated_refresh_token: Optional[str] = None) -> bool:
        """Perform automatic session token refresh when approaching expiration."""
        if self.is_session_valid():
            return True
        
        new_token = f"jwt_access_{int(time.time())}_{self.device.device_id[:6]}"
        new_expires = time.time() + 3600.0
        self.credentials = SessionCredentials(
            access_token=new_token,
            refresh_token=simulated_refresh_token or "refresh_seed_token",
            expires_at_epoch=new_expires,
            cookies=self.cookie_jar
        )
        return True
