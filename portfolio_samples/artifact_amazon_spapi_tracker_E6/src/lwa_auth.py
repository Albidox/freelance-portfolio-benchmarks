"""Login with Amazon (LWA) OAuth 2.0 token rotation engine."""

import time
from typing import Optional, Dict, Any
from src.models import AuthToken
from src.config import SPAPIConfig


class LWAAuthEngine:
    """Manages Login with Amazon (LWA) OAuth 2.0 token lifecycle and rotation."""

    def __init__(self, config: SPAPIConfig, token_lifetime_seconds: int = 3600, refresh_window_seconds: int = 300):
        self.config = config
        self.token_lifetime_seconds = token_lifetime_seconds
        self.refresh_window_seconds = refresh_window_seconds
        self._current_token: Optional[AuthToken] = None
        self.refresh_count: int = 0

    def get_valid_token(self, current_time: Optional[float] = None) -> str:
        """Return a valid LWA access token, proactively refreshing if expiring within the window."""
        now = current_time if current_time is not None else time.time()
        if self._current_token and not self._current_token.is_expiring(
            within_seconds=self.refresh_window_seconds, current_time=now
        ):
            return self._current_token.access_token

        # Proactively perform token rotation/refresh
        token_str = f"Atza|mock_valid_token_{int(now)}"
        self._current_token = AuthToken(
            access_token=token_str,
            token_type="bearer",
            expires_in=self.token_lifetime_seconds,
            refresh_token=self.config.lwa_refresh_token,
            created_at=now,
            expires_at=now + self.token_lifetime_seconds,
        )
        self.refresh_count += 1
        return self._current_token.access_token

    def force_refresh(self, current_time: Optional[float] = None) -> AuthToken:
        """Explicitly rotate token regardless of current expiration."""
        now = current_time if current_time is not None else time.time()
        token_str = f"Atza|mock_valid_token_{int(now)}"
        self._current_token = AuthToken(
            access_token=token_str,
            token_type="bearer",
            expires_in=self.token_lifetime_seconds,
            refresh_token=self.config.lwa_refresh_token,
            created_at=now,
            expires_at=now + self.token_lifetime_seconds,
        )
        self.refresh_count += 1
        return self._current_token
