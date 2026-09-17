import threading
import time
from collections import deque


class RateLimitBudgetExceeded(Exception):
    """Raised when a call would exceed the configured provider rate limits
    and it isn't worth waiting for the budget to free up (the caller should
    fall back to the non-LLM ranker instead of blocking further)."""


class SlidingWindowRateLimiter:
    """Client-side enforcement of a provider's published rate limits.

    Tracks request count and token count over rolling 1-minute and 1-day
    windows, so calls are throttled (or rejected) before they hit the
    provider and come back as a 429 -- the point is to fail predictably
    and fast into the fallback ranker rather than retry-loop against a
    rate limit repeatedly.

    In-memory and per-process: correct for a single API instance. A
    multi-instance deployment would need a shared store (e.g. Redis) to
    enforce these limits accurately across processes.
    """

    _MINUTE_SECONDS = 60.0
    _DAY_SECONDS = 86400.0

    def __init__(
        self,
        requests_per_minute: int,
        requests_per_day: int,
        tokens_per_minute: int,
        tokens_per_day: int,
        max_wait_seconds: float = 20.0,
        now_fn=time.monotonic,
        sleep_fn=time.sleep,
    ):
        self._rpm_limit = requests_per_minute
        self._rpd_limit = requests_per_day
        self._tpm_limit = tokens_per_minute
        self._tpd_limit = tokens_per_day
        self._max_wait_seconds = max_wait_seconds
        self._now = now_fn
        self._sleep = sleep_fn
        self._lock = threading.Lock()

        self._minute_requests: deque[float] = deque()
        self._day_requests: deque[float] = deque()
        self._minute_tokens: deque[tuple[float, int]] = deque()
        self._day_tokens: deque[tuple[float, int]] = deque()

    def _prune(self) -> None:
        now = self._now()
        while self._minute_requests and now - self._minute_requests[0] >= self._MINUTE_SECONDS:
            self._minute_requests.popleft()
        while self._day_requests and now - self._day_requests[0] >= self._DAY_SECONDS:
            self._day_requests.popleft()
        while self._minute_tokens and now - self._minute_tokens[0][0] >= self._MINUTE_SECONDS:
            self._minute_tokens.popleft()
        while self._day_tokens and now - self._day_tokens[0][0] >= self._DAY_SECONDS:
            self._day_tokens.popleft()

    def acquire(self, estimated_tokens: int) -> None:
        """Block until it's safe to make one call, reserving its budget.

        Raises RateLimitBudgetExceeded immediately if the daily request or
        token budget is already exhausted (waiting wouldn't help within a
        request's lifetime), or if clearing the per-minute limits would
        require waiting longer than max_wait_seconds.
        """
        waited = 0.0
        while True:
            with self._lock:
                self._prune()

                if len(self._day_requests) >= self._rpd_limit:
                    raise RateLimitBudgetExceeded("Daily request limit reached")
                if self._day_token_sum() + estimated_tokens > self._tpd_limit:
                    raise RateLimitBudgetExceeded("Daily token limit reached")

                rpm_ok = len(self._minute_requests) < self._rpm_limit
                tpm_ok = self._minute_token_sum() + estimated_tokens <= self._tpm_limit
                if rpm_ok and tpm_ok:
                    now = self._now()
                    self._minute_requests.append(now)
                    self._day_requests.append(now)
                    self._minute_tokens.append((now, estimated_tokens))
                    self._day_tokens.append((now, estimated_tokens))
                    return

            if waited >= self._max_wait_seconds:
                raise RateLimitBudgetExceeded(
                    "Per-minute rate limit would be exceeded and max wait exceeded"
                )
            self._sleep(1.0)
            waited += 1.0

    def record_actual_tokens(self, estimated_tokens: int, actual_tokens: int) -> None:
        """Correct a prior estimate with the real usage from the API
        response, so tracking doesn't drift over many calls."""
        delta = actual_tokens - estimated_tokens
        if delta == 0:
            return
        with self._lock:
            now = self._now()
            self._minute_tokens.append((now, delta))
            self._day_tokens.append((now, delta))

    def _minute_token_sum(self) -> int:
        return sum(tokens for _, tokens in self._minute_tokens)

    def _day_token_sum(self) -> int:
        return sum(tokens for _, tokens in self._day_tokens)
