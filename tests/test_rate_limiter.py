import pytest

from core.rate_limiter import RateLimitBudgetExceeded, SlidingWindowRateLimiter


class FakeClock:
    """Deterministic, controllable clock so tests don't do real waiting.

    sleep() advances the clock itself, exactly like a real blocking sleep
    would let time pass -- so a limiter loop that calls sleep_fn(1.0)
    genuinely observes 1 more second having elapsed on the next now_fn().
    """

    def __init__(self):
        self.now = 0.0

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


def make_limiter(clock: FakeClock, **overrides) -> SlidingWindowRateLimiter:
    defaults = dict(
        requests_per_minute=3,
        requests_per_day=10,
        tokens_per_minute=100,
        tokens_per_day=1000,
        max_wait_seconds=5.0,
        now_fn=clock.time,
        sleep_fn=clock.sleep,
    )
    defaults.update(overrides)
    return SlidingWindowRateLimiter(**defaults)


def test_allows_calls_within_all_limits(clock):
    limiter = make_limiter(clock)

    for _ in range(3):
        limiter.acquire(estimated_tokens=10)


def test_blocks_then_succeeds_once_minute_window_rolls_over(clock):
    limiter = make_limiter(clock, requests_per_minute=1, max_wait_seconds=120)

    limiter.acquire(estimated_tokens=10)
    # Second call must wait ~60s for the first request to fall out of the
    # 1-minute window; the fake clock advances exactly as sleep is called.
    limiter.acquire(estimated_tokens=10)

    assert clock.now >= 60.0


def test_raises_when_wait_would_exceed_max_wait_seconds(clock):
    limiter = make_limiter(clock, requests_per_minute=1, max_wait_seconds=5.0)

    limiter.acquire(estimated_tokens=10)
    with pytest.raises(RateLimitBudgetExceeded, match="max wait exceeded"):
        limiter.acquire(estimated_tokens=10)


def test_tokens_per_minute_limit_is_enforced(clock):
    limiter = make_limiter(clock, requests_per_minute=100, tokens_per_minute=50, max_wait_seconds=5.0)

    limiter.acquire(estimated_tokens=40)
    with pytest.raises(RateLimitBudgetExceeded):
        limiter.acquire(estimated_tokens=40)


def test_daily_request_limit_raises_immediately_without_waiting(clock):
    limiter = make_limiter(clock, requests_per_day=2, requests_per_minute=100, max_wait_seconds=999)

    limiter.acquire(estimated_tokens=1)
    limiter.acquire(estimated_tokens=1)
    with pytest.raises(RateLimitBudgetExceeded, match="Daily request limit"):
        limiter.acquire(estimated_tokens=1)

    # Must fail fast, not after waiting up to max_wait_seconds.
    assert clock.now == 0.0


def test_daily_token_limit_raises_immediately_without_waiting(clock):
    limiter = make_limiter(clock, tokens_per_day=100, requests_per_minute=100, max_wait_seconds=999)

    limiter.acquire(estimated_tokens=90)
    with pytest.raises(RateLimitBudgetExceeded, match="Daily token limit"):
        limiter.acquire(estimated_tokens=20)

    assert clock.now == 0.0


def test_old_entries_fall_out_of_the_minute_window(clock):
    limiter = make_limiter(clock, requests_per_minute=1, max_wait_seconds=999)

    limiter.acquire(estimated_tokens=10)
    clock.now += 61  # manually advance past the 1-minute window
    limiter.acquire(estimated_tokens=10)  # should not block at all

    assert clock.now == 61


def test_record_actual_tokens_increases_minute_usage_on_underestimate():
    from core.rate_limiter import SlidingWindowRateLimiter as _Limiter

    clock = FakeClock()
    limiter = _Limiter(
        requests_per_minute=100,
        requests_per_day=100,
        tokens_per_minute=100,
        tokens_per_day=1000,
        now_fn=clock.time,
        sleep_fn=clock.sleep,
    )
    limiter.acquire(estimated_tokens=10)
    limiter.record_actual_tokens(estimated_tokens=10, actual_tokens=50)

    # Budget should now reflect 50 used, not 10 -- a second call for 60 more
    # would push the minute total to 110, over the 100 limit.
    with pytest.raises(RateLimitBudgetExceeded):
        limiter.acquire(estimated_tokens=60)


def test_record_actual_tokens_decreases_minute_usage_on_overestimate(clock):
    limiter = make_limiter(clock, tokens_per_minute=100)

    limiter.acquire(estimated_tokens=90)
    limiter.record_actual_tokens(estimated_tokens=90, actual_tokens=20)

    # Budget freed back up -- a call for 70 more now fits (20 + 70 = 90 <= 100).
    limiter.acquire(estimated_tokens=70)
