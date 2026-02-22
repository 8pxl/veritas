import random
import time
from typing import Callable, TypeVar

T = TypeVar("T")

# Error codes from Groq that will never succeed on retry with the same input.
_NON_RETRYABLE_CODES = frozenset({
    "tool_use_failed",
    "json_validate_failed",
})


def groq_call_with_retry(
    fn: Callable[[], T],
    *,
    max_retries: int = 5,
    initial_delay: float = 0.8,
    op_name: str = "groq_call",
) -> T:
    """Run a Groq call with bounded retries, backoff, and jitter."""
    delay = initial_delay
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as e:
            # Don't retry errors that will always fail with the same input
            code = ""
            if hasattr(e, "body") and isinstance(e.body, dict):
                code = e.body.get("error", {}).get("code", "")
            if code in _NON_RETRYABLE_CODES:
                raise

            if attempt == max_retries - 1:
                raise
            print(
                f"{op_name}: {type(e).__name__}; retrying ({attempt + 1}/{max_retries})"
            )
            time.sleep(delay + random.uniform(0.0, 0.25))
            delay = min(delay * 2, 8.0)
    raise RuntimeError(f"{op_name}: exhausted retries")
