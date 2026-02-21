import csv
import json
import os
from rag import *
from judge import judge_videos_batch, deduplicate_videos
from datetime import datetime
from dotenv import load_dotenv
from googleapiclient.discovery import build
from groq import Groq

from youtube_types import (
    SearchListResponse,
    CompanyData,
    VideoInfo,
    EventVideos,
    CompanyEvent,
)


def parse_iso_date(date_str: str) -> datetime:
    """Parse ISO 8601 date string to datetime object."""
    return datetime.fromisoformat(date_str.replace("Z", "+00:00"))


def search_videos(
    youtube, search_query: str, year: int, max_results: int = 10
) -> list[VideoInfo]:
    """Search for videos for a specific search query and year."""

    # Date range for the year
    published_after = f"{year}-01-01T00:00:00Z"
    published_before = f"{year + 1}-01-01T00:00:00Z"

    try:
        request = youtube.search().list(
            part="snippet",
            q=f"search_query {year}",
            type="video",
            maxResults=max_results,
            publishedAfter=published_after,
            publishedBefore=published_before,
            order="date",
            relevanceLanguage="en",
        )
        response: SearchListResponse = request.execute()

        videos = []
        for item in response.get("items", []):
            resource_id = item["id"]
            if resource_id["kind"] != "youtube#video":
                continue
            snippet = item["snippet"]

            # Get the best available thumbnail
            thumbnails = snippet["thumbnails"]
            thumbnail_url = (
                thumbnails.get("high", {}).get("url")
                or thumbnails.get("medium", {}).get("url")
                or thumbnails.get("default", {}).get("url", "")
            )

            video_info: VideoInfo = {
                "video_id": resource_id.get("videoId", ""),  # type: ignore[typeddict-item]
                "title": snippet["title"],
                "description": snippet["description"],
                "channel_title": snippet["channelTitle"],
                "published_at": snippet["publishedAt"],
                "thumbnail_url": thumbnail_url,
            }
            videos.append(video_info)

        return videos

    except Exception as e:
        print(f"Error searching for '{search_query}' ({year}): {e}")
        return []


def fetch_company_videos(
    youtube,
    groq_client: Groq,
    symbol: str,
    company_name: str,
    sector: str,
    years: range,
) -> CompanyData:
    """Fetch all videos for a company using Groq-discovered events."""
    print(f"\nFetching videos for {symbol} - {company_name}")

    # Step 1: Discover events for this company using Groq
    print("  Discovering company events with Groq...")
    discovery_result = discover_company_events(
        groq_client, company_name, symbol, sector
    )
    discovered_events = discovery_result["events"]

    if not discovered_events:
        print("  No events discovered, skipping company")
        return CompanyData(symbol=symbol, name=company_name, events=[])

    print(f"  Found {len(discovered_events)} events:")
    for event in discovered_events:
        print(f"    - {event['event_name']}")

    # Step 2: Search for videos for each discovered event, judge, deduplicate
    event_videos_list: list[EventVideos] = []

    for event in discovered_events:
        all_videos: list[VideoInfo] = []

        print(f"\n  Searching for: {event['event_name']}")

        # Search for each year separately
        for year in years:
            print(event["search_query"])
            raw_videos = search_videos(youtube, event["search_query"], year)
            if raw_videos:
                print(f"    {year}: {len(raw_videos)} raw results", end="")

                # Judge relevance — returns the single best video or None
                best = judge_videos_batch(
                    groq_client,
                    raw_videos,
                    event_name=event["event_name"],
                    company_name=company_name,
                )
                if best is not None:
                    print(f" -> kept 1 (score {best.get('relevance_score', '?')})")
                    all_videos.append(best)
                else:
                    print(" -> none relevant")

        # Deduplicate across all years (same video can appear in multiple searches)
        all_videos = deduplicate_videos(all_videos)

        # Sort all videos by date (newest first)
        all_videos.sort(key=lambda v: parse_iso_date(v["published_at"]), reverse=True)

        event_videos: EventVideos = {
            "event_name": event["event_name"],
            "search_query": event["search_query"],
            "videos": all_videos,
        }

        event_videos_list.append(event_videos)
        print(f"    Final: {len(all_videos)} videos (after dedup + judge)")

    company_data: CompanyData = {
        "symbol": symbol,
        "name": company_name,
        "events": event_videos_list,
    }

    return company_data


def main():
    load_dotenv()

    # Get API keys
    yt_api_key = os.getenv("YT_KEY")
    groq_api_key = os.getenv("GROQ_API_KEY")

    if not yt_api_key:
        print("Error: YT_KEY not found in environment variables")
        return

    if not groq_api_key:
        print("Error: GROQ_API_KEY not found in environment variables")
        return

    # Initialize API clients
    youtube = build("youtube", "v3", developerKey=yt_api_key)
    groq_client = Groq(api_key=groq_api_key)

    # Get year range from user
    years_input = input("Enter year range (e.g., '2020 2025'): ").split()
    start_year, end_year = int(years_input[0]), int(years_input[1])
    years = range(start_year, end_year + 1)

    print(f"Searching for videos from {start_year} to {end_year}")

    # Read SP500 companies from CSV
    companies = []
    csv_path = "data/sp500.csv"

    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                companies.append(
                    {
                        "symbol": row["Symbol"],
                        "name": row["Shortname"],
                        "sector": row.get("Sector", ""),
                    }
                )
    except FileNotFoundError:
        print(f"Error: {csv_path} not found")
        return

    print(f"\nFound {len(companies)} companies to process")

    # Optional: limit number of companies for testing
    limit = (
        input("Process all companies? (y/n, or enter number to limit): ")
        .strip()
        .lower()
    )
    if limit != "y" and limit != "yes":
        if limit.isdigit():
            companies = companies[: int(limit)]
        else:
            companies = companies[:5]  # Default to 5 for testing

    print(f"Processing {len(companies)} companies\n")

    # Fetch videos for each company
    all_company_data = []

    for i, company in enumerate(companies, 1):
        print(f"\n{'=' * 60}")
        print(f"[{i}/{len(companies)}]")

        try:
            company_data = fetch_company_videos(
                youtube,
                groq_client,
                company["symbol"],
                company["name"],
                company["sector"],
                years,
            )
            all_company_data.append(company_data)
        except Exception as e:
            print(f"Error processing {company['name']}: {e}")
            continue

    # Save to JSON file
    output_file = "out/sp500_youtube_videos_groq.json"
    os.makedirs("out", exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_company_data, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print(f"Results saved to {output_file}")

    # Print summary statistics
    total_events = sum(len(company["events"]) for company in all_company_data)
    total_videos = sum(
        sum(len(event["videos"]) for event in company["events"])
        for company in all_company_data
    )

    print(f"\nSummary:")
    print(f"  Companies processed: {len(all_company_data)}")
    print(f"  Total events discovered: {total_events}")
    print(f"  Total videos fetched: {total_videos}")
    print(f"  Average events per company: {total_events / len(all_company_data):.1f}")
    print(f"  Average videos per company: {total_videos / len(all_company_data):.1f}")


if __name__ == "__main__":
    main()
