"""Discover company events using Groq AI."""

import os
import json
from typing import TypedDict
from groq import Groq
from prompts import load_prompt


class CompanyEvent(TypedDict):
    """Information about a company event."""

    event_name: str
    search_query: str
    description: str
    frequency: str  # e.g., "annual", "quarterly", "irregular"


class CompanyEvents(TypedDict):
    """Collection of events for a company."""

    symbol: str
    company_name: str
    events: list[CompanyEvent]


def _web_search(query: str, max_results: int = 5) -> str:
    """Run a web search and return formatted results."""
    from ddgs import DDGS

    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=max_results))
    if not results:
        return "(no results)"
    return "\n".join(f"- {r['title']}: {r['body']}" for r in results)


_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": ("Search the web "),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query",
                }
            },
            "required": ["query"],
        },
    },
}


def discover_company_events(
    client: Groq, company_name: str, symbol: str, industry: str = ""
) -> CompanyEvents:
    """
    Use Groq to discover what types of recurring events a company hosts
    that would have YouTube videos.

    Args:
        client: Groq client instance
        company_name: Full company name
        symbol: Stock symbol
        industry: Company industry/sector (optional, helps with context)

    Returns:
        CompanyEvents with discovered events
    """

    industry_context = f" in the {industry} industry" if industry else ""

    system_prompt = load_prompt("event_discovery_system")
    user_prompt = load_prompt("event_discovery_user").format(
        company_name=company_name,
        symbol=symbol,
        industry_context=industry_context,
    )

    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        for _ in range(8):
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                tools=[_SEARCH_TOOL],
                temperature=0,
            )
            msg = resp.choices[0].message

            if msg.tool_calls:
                messages.append(msg)
                for tc in msg.tool_calls:
                    if tc.function.name == "web_search":
                        args = json.loads(tc.function.arguments)
                        print(f"  Searching: {args['query']}")
                        result = _web_search(args["query"])
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "content": result,
                            }
                        )
                        
            else:
                # Model finished researching — append its summary
                messages.append(msg)
                break

        chat_completion = client.chat.completions.create(
            messages=messages,
            model="openai/gpt-oss-20b",
            temperature=0,
            max_tokens=2000,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "company_events",
                    # "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "event_name": {"type": "string"},
                            "search_query": {"type": "string"},
                        },
                        "required": ["event_name", "search_query"],
                        "additionalProperties": False,
                    },
                },
            },
        )

        response_text = chat_completion.choices[0].message.content

        # Parse the JSON response
        events = json.loads(response_text)

        return CompanyEvents(
            symbol=symbol,
            company_name=company_name,
            events=events,
        )

    except json.JSONDecodeError as e:
        print(f"Error parsing Groq response for {company_name}: {e}")
        print(f"Response was: {response_text}")
        return CompanyEvents(
            symbol=symbol,
            company_name=company_name,
            events=[],
        )
    except Exception as e:
        print(f"Error discovering events for {company_name}: {e}")
        return CompanyEvents(
            symbol=symbol,
            company_name=company_name,
            events=[],
        )


def main():
    """Test event discovery with a few sample companies."""
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    test_companies = [
        {"name": "Apple Inc.", "symbol": "AAPL", "industry": "Technology"},
        {"name": "Google", "symbol": "GOOGL", "industry": "Technology"},
        {"name": "JPMorgan Chase", "symbol": "JPM", "industry": "Financial Services"},
    ]

    for company in test_companies:
        print(f"\nDiscovering events for {company['name']}...")
        events = discover_company_events(
            client, company["name"], company["symbol"], company["industry"]
        )

        print(f"\nFound {len(events['events'])} events:")
        for event in events["events"]:
            print(f"    Query: {event['search_query']}")


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    main()
