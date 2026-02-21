import csv
import json
import os
from rag import *
from judge import judge_videos_batch, deduplicate_videos
from dotenv import load_dotenv
from groq import Groq
import yt_dlp
from youtube_types import (
    CompanyData,
    VideoInfo,
    EventVideos,
    CompanyEvent,
)
def search_videos(
    search_query: str, year: int, max_results: int = 10
) -> list[VideoInfo]:
    """Search YouTube for videos using yt-dlp (no API key required)."""
    query = f"ytsearch{max_results}:{search_query} {year}"
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",
        "skip_download": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(query, download=False)
        videos: list[VideoInfo] = []
        for entry in (result or {}).get("entries", []):
            if entry is None:
                continue
            video_id = entry.get("id", "")
            videos.append(
                {
                    "video_id": video_id,
                    "title": entry.get("title", ""),
                    "channel_title": entry.get("channel")
                    or entry.get("uploader")
                    or "",
                    "thumbnail_url": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
                    "view_count": entry.get("view_count"),
                    "duration": entry.get("duration"),
                    "channel_is_verified": entry.get(
                        "channel_is_verified", False
                    ),
                }
            )
        return videos
    except Exception as e:
        print(f"Error searching for '{search_query}' ({year}): {e}")
        return []
def fetch_company_videos(
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
            print(f"    {event['search_query']} {year}")
            raw_videos = search_videos(event["search_query"], year)
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
                    print(
                        f" -> kept 1 (score {best.get('relevance_score', '?')})"
                    )
                    all_videos.append(best)
                else:
                    print(" -> none relevant")
        # Deduplicate across all years (same video can appear in multiple searches)
        all_videos = deduplicate_videos(all_videos)
        # Sort by relevance score (highest first)
        all_videos.sort(
            key=lambda v: v.get("relevance_score", 0), reverse=True
        )
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
    # Get API key
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        print("Error: GROQ_API_KEY not found in environment variables")
        return
    # Initialize Groq client
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
        input(
            "Process all companies? (y/n, or enter number to limit): "
        )
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
    total_events = sum(
        len(company["events"]) for company in all_company_data
    )
    total_videos = sum(
        sum(len(event["videos"]) for event in company["events"])
        for company in all_company_data
    )
    print(f"\nSummary:")
    print(f"  Companies processed: {len(all_company_data)}")
    print(f"  Total events discovered: {total_events}")
    print(f"  Total videos fetched: {total_videos}")
    print(
        f"  Average events per company: {total_events / len(all_company_data):.1f}"
    )
    print(
        f"  Average videos per company: {total_videos / len(all_company_data):.1f}"
    )
if __name__ == "__main__":
    main()
