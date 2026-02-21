"""Discover company events using Groq AI."""

import os
import json
from typing import TypedDict
from groq import Groq


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


def discover_company_events(
    client: Groq, company_name: str, symbol: str, industry: str = ""
) -> CompanyEvents:
    """
    Use Groq to discover what types of events a company hosts that would have YouTube videos.

    Args:
        client: Groq client instance
        company_name: Full company name
        symbol: Stock symbol
        industry: Company industry/sector (optional, helps with context)

    Returns:
        CompanyEvents with discovered events
    """

    industry_context = f" in the {industry} industry" if industry else ""

    prompt = f"""You are a corporate events research assistant. For the company {company_name} ({symbol}){industry_context}, identify the specific PUBLIC events, conferences, and presentations they regularly host or participate in that would have videos on YouTube.

Think about:
1. Company-specific annual conferences (like Apple's WWDC, Google I/O, Salesforce Dreamforce)
2. Regular investor events (earnings calls, investor days, shareholder meetings)
3. Product launches and keynotes
4. Developer conferences
5. CEO interviews and appearances
6. Press conferences

For EACH event type, provide:
- The specific name of the event (e.g., "WWDC" not just "developer conference") 
- An optimal YouTube search query to find these videos. Don't include any dates.

Return your response as a JSON array of events. Each event should have this structure:
{{
  "event_name": "Event Name",
  "search_query": "optimal search terms for YouTube",
}}

Focus on events that:
- Are likely to have video recordings on YouTube
- Are public-facing (not internal meetings)
- Happen regularly or are significant enough to search for
- Use the company's actual event names when applicable

Return ONLY the JSON array, no other text.

MAKE NO MISTAKES.

YOU MUST CALL WEB SEARCH AT LEAST ONCE PER REQUEST.
"""

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at researching corporate events and public appearances. You provide accurate, well-researched information about company-specific events that have YouTube video coverage.",
                },
                {"role": "user", "content": prompt},
            ],
            model="openai/gpt-oss-120b",
            temperature=0,
            max_tokens=2000,
            response_format = {
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
                        "additionalProperties": False
                    }
                }
            }
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
