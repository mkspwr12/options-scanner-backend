"""Tests for Massive provider rate limiting."""
import time
from unittest.mock import MagicMock, patch

import pytest

from app.providers.massive_provider import MassiveProvider


class TestMassiveRateLimiting:
    """Test rate limiting behavior."""

    def test_rate_limit_enforces_minimum_delay(self):
        """Verify minimum delay between requests is enforced."""
        provider = MassiveProvider(api_key="test_key", min_request_interval=0.2)
        
        with patch("app.providers.massive_provider.urlopen") as mock_urlopen:
            # Mock successful responses
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"results": []}'
            mock_resp.__enter__ = lambda self: mock_resp
            mock_resp.__exit__ = lambda *args: None
            mock_urlopen.return_value = mock_resp
            
            # Make two requests and measure time
            start = time.time()
            provider._get_json("/test", {})
            provider._get_json("/test", {})
            elapsed = time.time() - start
            
            # Should have at least 0.2s delay between requests
            assert elapsed >= 0.2, f"Expected >= 0.2s, got {elapsed:.3f}s"
            assert mock_urlopen.call_count == 2

    def test_rate_limit_retry_on_429(self):
        """Verify exponential backoff on 429 rate limit errors."""
        from urllib.error import HTTPError
        
        provider = MassiveProvider(api_key="test_key", min_request_interval=0.05, max_retries=3)
        
        with patch("app.providers.massive_provider.urlopen") as mock_urlopen:
            # Mock 429 errors followed by success
            error = HTTPError(url="", code=429, msg="Too Many Requests", hdrs={}, fp=None)
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"results": []}'
            mock_resp.__enter__ = lambda self: mock_resp
            mock_resp.__exit__ = lambda *args: None
            
            # First two attempts fail with 429, third succeeds
            mock_urlopen.side_effect = [error, error, mock_resp]
            
            start = time.time()
            result = provider._get_json("/test", {})
            elapsed = time.time() - start
            
            # Should have exponential backoff: 1s + 2s = 3s minimum
            assert elapsed >= 3.0, f"Expected >= 3s backoff, got {elapsed:.3f}s"
            assert mock_urlopen.call_count == 3
            assert result == {"results": []}

    def test_rate_limit_max_retries_exceeded(self):
        """Verify error raised when max retries exceeded."""
        from urllib.error import HTTPError
        
        provider = MassiveProvider(api_key="test_key", min_request_interval=0.05, max_retries=2)
        
        with patch("app.providers.massive_provider.urlopen") as mock_urlopen:
            # Mock persistent 429 errors
            error = HTTPError(url="", code=429, msg="Too Many Requests", hdrs={}, fp=None)
            mock_urlopen.side_effect = error
            
            with pytest.raises(RuntimeError, match="rate limit exceeded"):
                provider._get_json("/test", {})
            
            # Should have tried max_retries times
            assert mock_urlopen.call_count == 2

    def test_rate_limit_non_429_error_not_retried(self):
        """Verify non-429 HTTP errors are not retried."""
        from urllib.error import HTTPError
        
        provider = MassiveProvider(api_key="test_key", min_request_interval=0.05, max_retries=3)
        
        with patch("app.providers.massive_provider.urlopen") as mock_urlopen:
            # Mock 404 error
            error = HTTPError(url="", code=404, msg="Not Found", hdrs={}, fp=None)
            mock_urlopen.side_effect = error
            
            with pytest.raises(RuntimeError, match="HTTP 404"):
                provider._get_json("/test", {})
            
            # Should only try once (no retry for non-429)
            assert mock_urlopen.call_count == 1
