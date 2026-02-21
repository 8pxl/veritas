import random
import time
from typing import Callable, TypeVar

T = TypeVar("T")


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
            if attempt == max_retries - 1:
                raise
            print(
                f"{op_name}: {type(e).__name__}; retrying ({attempt + 1}/{max_retries})"
            )
            time.sleep(delay + random.uniform(0.0, 0.25))
            delay = min(delay * 2, 8.0)
    raise RuntimeError(f"{op_name}: exhausted retries")
