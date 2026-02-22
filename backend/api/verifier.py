"""LLM-powered proposition verifier using Groq with web search."""

import os
import json
import time
import random
from datetime import datetime, timezone
from typing import TypedDict

from groq import Groq
from groq.types.chat import ChatCompletionToolParam
from ddgs import DDGS


class VerificationResult(TypedDict):
    verdict: str  # "true", "false", or "future"
    reasoning: str


def _groq_retry(fn, *, max_retries=5, initial_delay=0.8, op_name="groq_call"):
    """Run a Groq call with bounded retries, backoff, and jitter."""
    delay = initial_delay
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            print(f"{op_name}: {type(e).__name__}; retrying ({attempt + 1}/{max_retries})")
            time.sleep(delay + random.uniform(0.0, 0.25))
            delay = min(delay * 2, 8.0)
    raise RuntimeError(f"{op_name}: exhausted retries")


def _web_search(query: str, max_results: int = 5) -> str:
    """Run a web search and return formatted results."""
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=max_results))
    if not results:
        return "(no results)"
    return "\n".join(f"- {r['title']}: {r['body']}" for r in results)


_SEARCH_TOOL: ChatCompletionToolParam = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search the web for evidence to verify a corporate statement.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query to find evidence",
                }
            },
            "required": ["query"],
        },
    },
}

_SYSTEM_PROMPT = """\
You are a rigorous fact-checker for corporate statements. Your job is to determine \
whether a given statement made by a corporate speaker is TRUE, FALSE, or can only \
be verified in the FUTURE.

Guidelines:
- Use the web_search tool to find evidence supporting or refuting the statement.
- Consider the speaker's organization and role when evaluating credibility.
- Consider the date the statement was made and the date it should be verified by.
- A statement is "future" if it refers to plans, forecasts, or events that have not \
yet occurred and cannot be verified with current information.
- A statement is "true" if you find strong supporting evidence.
- A statement is "false" if you find strong contradicting evidence.
- Be thorough — search multiple angles before reaching a conclusion.
- After gathering enough evidence, provide your final verdict with clear reasoning.\
"""


def verify_proposition(
    statement: str,
    speaker_name: str,
    speaker_org: str,
    video_title: str,
    date_stated: datetime,
    verify_at: datetime,
) -> VerificationResult:
    """
    Verify a single proposition using multi-turn Groq chat with web search.

    Returns a VerificationResult with verdict and reasoning.
    """
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    now = datetime.now(timezone.utc)

    user_prompt = (
        f"Please verify the following statement:\n\n"
        f'Statement: "{statement}"\n'
        f"Speaker: {speaker_name} ({speaker_org})\n"
        f"Video: {video_title}\n"
        f"Date stated: {date_stated.strftime('%Y-%m-%d')}\n"
        f"Verify by: {verify_at.strftime('%Y-%m-%d')}\n"
        f"Current date: {now.strftime('%Y-%m-%d')}\n\n"
        f"Search for evidence and determine if this statement is true, false, "
        f"or can only be verified in the future."
    )

    messages: list[dict] = [  # type: ignore[type-arg]
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    # Multi-turn research phase (up to 8 rounds of tool use)
    for _ in range(8):
        resp = _groq_retry(
            lambda: client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,  # type: ignore[arg-type]
                tools=[_SEARCH_TOOL],
                temperature=0,
            ),
            op_name="verify_research",
        )
        msg = resp.choices[0].message

        if msg.tool_calls:
            messages.append(msg)  # type: ignore[arg-type]
            for tc in msg.tool_calls:
                if tc.function.name == "web_search":
                    args = json.loads(tc.function.arguments)
                    print(f"  [verifier] Searching: {args['query']}")
                    result = _web_search(args["query"])
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": result,
                        }
                    )
        else:
            messages.append(msg)  # type: ignore[arg-type]
            break

    # Structured output phase — extract verdict
    messages.append(
        {
            "role": "user",
            "content": (
                "Based on your research, provide your final verdict as JSON with "
                'exactly two fields: "verdict" (one of "true", "false", "future") '
                'and "reasoning" (a brief explanation).'
            ),
        }
    )

    final_resp = _groq_retry(
        lambda: client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,  # type: ignore[arg-type]
            temperature=0,
            response_format={"type": "json_object"},
        ),
        op_name="verify_verdict",
    )

    raw = final_resp.choices[0].message.content or ""
    try:
        parsed = json.loads(raw)
        verdict = parsed.get("verdict", "future").lower()
        if verdict not in ("true", "false", "future"):
            verdict = "future"
        reasoning = parsed.get("reasoning", "")
    except json.JSONDecodeError:
        verdict = "future"
        reasoning = f"Failed to parse LLM response: {raw[:500]}"

    return VerificationResult(verdict=verdict, reasoning=reasoning)


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    test_cases = [
        {
            "statement": "Apple reported over $380 billion in revenue for fiscal year 2023.",
            "speaker_name": "Tim Cook",
            "speaker_org": "Apple Inc.",
            "video_title": "Apple Q4 2023 Earnings Call",
            "date_stated": datetime(2023, 11, 2),
            "verify_at": datetime(2024, 1, 1),
        },
        {
            "statement": "Tesla will produce 20 million vehicles per year by 2030.",
            "speaker_name": "Elon Musk",
            "speaker_org": "Tesla Inc.",
            "video_title": "Tesla Investor Day 2023",
            "date_stated": datetime(2023, 3, 1),
            "verify_at": datetime(2030, 12, 31),
        },
        {
            "statement": "Microsoft acquired GitHub for $7.5 billion in 2018.",
            "speaker_name": "Satya Nadella",
            "speaker_org": "Microsoft Corporation",
            "video_title": "Microsoft Build 2019 Keynote",
            "date_stated": datetime(2019, 5, 6),
            "verify_at": datetime(2019, 6, 1),
        },
    ]

    print("=" * 60)
    print("Verifier stability test")
    print("=" * 60)

    for i, tc in enumerate(test_cases, 1):
        print(f"\n--- Test {i}: {tc['statement'][:60]}...")
        try:
            result = verify_proposition(**tc)
            print(f"  Verdict:   {result['verdict']}")
            print(f"  Reasoning: {result['reasoning'][:200]}")
        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {e}")

    print("\n" + "=" * 60)
    print("Done")
