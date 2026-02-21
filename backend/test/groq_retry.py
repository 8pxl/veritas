import random
import time
from typing import Callable, TypeVar

from groq import (
    APIConnectionError,
    APIError,
    APIResponseValidationError,
    APIStatusError,
    APITimeoutError,
    BadRequestError,
    InternalServerError,
    RateLimitError,
)

T = TypeVar("T")


def groq_call_with_retry(
    fn: Callable[[], T],
    *,
    max_retries: int = 5,
    initial_delay: float = 0.8,
    retry_tool_use_failed: bool = False,
    retry_json_validate_failed: bool = True,
    op_name: str = "groq_call",
) -> T:
    delay = initial_delay
    for attempt in range(max_retries):
        try:
            return fn()
        except BadRequestError as e:
            code = getattr(e, "body", {}).get("error", {}).get("code")
            should_retry_bad_request = (
                (code == "tool_use_failed" and retry_tool_use_failed)
                or (code == "json_validate_failed" and retry_json_validate_failed)
            )
            if should_retry_bad_request and attempt < max_retries - 1:
                print(
                    f"{op_name}: {code}; retrying ({attempt + 1}/{max_retries})"
                )
                time.sleep(delay + random.uniform(0.0, 0.25))
                delay = min(delay * 2, 8.0)
                continue
            raise
        except (
            RateLimitError,
            APITimeoutError,
            APIConnectionError,
            InternalServerError,
            APIError,
            APIResponseValidationError,
        ):
            if attempt == max_retries - 1:
                raise
            print(f"{op_name}: transient error; retrying ({attempt + 1}/{max_retries})")
            time.sleep(delay + random.uniform(0.0, 0.25))
            delay = min(delay * 2, 8.0)
        except APIStatusError as e:
            status_code = getattr(e, "status_code", None)
            should_retry = status_code is not None and status_code >= 500
            if not should_retry or attempt == max_retries - 1:
                raise
            print(
                f"{op_name}: status {status_code}; retrying ({attempt + 1}/{max_retries})"
            )
            time.sleep(delay + random.uniform(0.0, 0.25))
            delay = min(delay * 2, 8.0)
    raise RuntimeError(f"{op_name}: exhausted retries")
