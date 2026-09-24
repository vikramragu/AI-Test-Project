import logging
from contextvars import ContextVar

from config import get_settings

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

_configured = False


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def setup_logging() -> None:
    """Configure the root logger once, from settings.log_level.

    Every log line includes a request_id (set per-request via
    request_id_var by api/routes/recommendations.py) so every log line
    from a single request -- across filter.py, llm_client.py, fallback.py
    -- can be correlated after the fact, even under concurrent requests.
    Idempotent so it's safe to call from api/main.py, tests, or scripts.
    """
    global _configured
    if _configured:
        return

    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    handler = logging.StreamHandler()
    handler.addFilter(_RequestIdFilter())
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s [%(request_id)s]: %(message)s")
    )

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)
    _configured = True
