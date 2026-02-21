import csv
import json
import os
from youtube_types import *
from datetime import datetime
from typing import cast
from dotenv import load_dotenv
from googleapiclient.discovery import build

CATEGORIES = {
    "investor_days": "investor day",
    "earnings_calls": "earnings call",
    "press_conferences": "press conference",
    "product_launches": "product launch",
    "public_interviews": "interview CEO",
}

# Years to search (adjust as needed)
years_range = tuple(map(int, input("enter start dates (space seperated): ").split()))
YEARS = range(years_range[0], years_range[1])


def parse_iso_date(date_str: str) -> datetime:
    """Parse ISO 8601 date string to datetime object."""
    return datetime.fromisoformat(date_str.replace("Z", "+00:00"))


def search_videos(
    youtube, company_name: str, category: str, year: int, max_results: int = 10
) -> list[VideoInfo]:
    """Search for videos for a specific company, category, and year."""
    query = f"{company_name} {category} {year}"

    # Date range for the year
    published_after = f"{year}-01-01T00:00:00Z"
    published_before = f"{year + 1}-01-01T00:00:00Z"

    try:
        request = youtube.search().list(
            part="snippet",
            q=query,
            type="video",
            maxResults=max_results,
            publishedAfter=published_after,
            publishedBefore=published_before,
            order="date",  # Sort by date
            relevanceLanguage="en",
        )
        response: SearchListResponse = request.execute()

        videos = []
        for item in response.get("items", []):
            if item["id"]["kind"] == "youtube#video":
                snippet = item["snippet"]

                # Get the best available thumbnail
                thumbnails = snippet["thumbnails"]
                thumbnail_url = (
                    thumbnails.get("high", {}).get("url")
                    or thumbnails.get("medium", {}).get("url")
                    or thumbnails.get("default", {}).get("url", "")
                )

                video_info: VideoInfo = {
                    "video_id": item["id"]["videoId"],
                    "title": snippet["title"],
                    "description": snippet["description"],
                    "channel_title": snippet["channelTitle"],
                    "published_at": snippet["publishedAt"],
                    "thumbnail_url": thumbnail_url,
                }
                videos.append(video_info)

        return videos

    except Exception as e:
        print(f"Error searching for {company_name} - {category} ({year}): {e}")
        return []


def fetch_company_videos(youtube, symbol: str, company_name: str) -> CompanyData:
    """Fetch all videos for a company across all categories and years."""
    print(f"Fetching videos for {symbol} - {company_name}")

    category_videos: CategoryVideos = {
        "investor_days": [],
        "earnings_calls": [],
        "press_conferences": [],
        "product_launches": [],
        "public_interviews": [],
    }

    for category_key, category_query in CATEGORIES.items():
        all_videos = []

        # Search for each year separately
        for year in YEARS:
            videos = search_videos(youtube, company_name, category_query, year)
            all_videos.extend(videos)

        # Sort all videos by date (newest first)
        all_videos.sort(key=lambda v: parse_iso_date(v["published_at"]), reverse=True)

        category_videos[category_key] = all_videos
        print(f"  {category_key}: {len(all_videos)} videos")

    company_data: CompanyData = {
        "symbol": symbol,
        "name": company_name,
        "videos": category_videos,
    }

    return company_data


def main():
    """Main function to fetch videos for all SP500 companies."""
    load_dotenv()
    api_key = os.getenv("YT_KEY")

    if not api_key:
        print("Error: YT_KEY not found in environment variables")
        return

    youtube = build("youtube", "v3", developerKey=api_key)

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
                    }
                )
    except FileNotFoundError:
        print(f"Error: {csv_path} not found")
        return

    print(f"Found {len(companies)} companies to process\n")

    # Fetch videos for each company
    all_company_data = []

    for i, company in enumerate(companies, 1):
        if (i >= 2): 
            break
        print(f"[{i}/{len(companies)}]")
        company_data = fetch_company_videos(youtube, company["symbol"], company["name"])
        all_company_data.append(company_data)
        print()

    # Save to JSON file
    output_file = "out/sp500_youtube_videos.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_company_data, f, indent=2, ensure_ascii=False)

    print(f"Results saved to {output_file}")

    # Print summary statistics
    total_videos = sum(
        sum(len(videos) for videos in company["videos"].values())
        for company in all_company_data
    )
    print(f"\nTotal videos fetched: {total_videos}")


if __name__ == "__main__":
    main()
