 # yt-dlp Refactor Plan
## Problem
The YouTube Data API v3 has a quota of 10,000 units/day. Each `search.list` call
costs 100 units, so we're capped at ~100 searches/day. With 500 companies x
multiple events x multiple years, we burn through quota immediately.
## Solution
Replace the `google-api-python-client` YouTube search with `yt-dlp`, which
scrapes YouTube search results directly with no API key and no quota.
## Key Findings from Investigation
| | Google API | yt-dlp flat mode |
|---|---|---|
| Cost | 100 quota units/search | Free, no limits |
| Speed | ~0.5s | ~1s |
| Fields | title, description, channel, publishedAt, thumbnails | title, channel, view_count, duration, url, channel_is_verified |
| Description | Full | Not available in flat mode |
| Date filtering | Server-side (publishedAfter/Before) | Not available in flat mode (upload_date is null) |
| Auth | Requires API key | None |
**Trade-offs accepted:**
- No `description` field -- judge will use title + channel + view_count + duration
  instead. Title and channel are the strongest relevance signals anyway.
- No server-side date filtering -- include year in the search query string
  (e.g. "Apple WWDC 2024 keynote") to get year-relevant results.
## Files to Change
### 1. `src/main.py` -- Replace `search_videos()`
**Current:** Uses `google-api-python-client` to call `youtube.search().list()`.
**New:** Use `yt-dlp` as a Python library (`yt_dlp.YoutubeDL`) to search.
```
Before:
  search_videos(youtube, search_query, year, max_results=10) -> list[VideoInfo]
    - youtube.search().list(q=..., publishedAfter=..., publishedBefore=...)
After:
  search_videos(search_query, year, max_results=10) -> list[VideoInfo]
    - yt_dlp.YoutubeDL with extract_flat='in_playlist'
    - query: f"ytsearch{max_results}:{search_query} {year}"
```
The `youtube` client parameter is removed from `search_videos()` and
`fetch_company_videos()` since we no longer need the Google API client.
**Also fix existing bug:** Line 37 has `f"search_query {year}"` (literal string)
instead of `f"{search_query} {year}"` (variable interpolation).
#### Field mapping (yt-dlp flat -> VideoInfo)
| VideoInfo field | yt-dlp flat field |
|---|---|
| `video_id` | `id` |
| `title` | `title` |
| `description` | `""` (not available in flat mode) |
| `channel_title` | `channel` or `uploader` |
| `published_at` | `""` (not available in flat mode) |
| `thumbnail_url` | Constructed from video ID: `https://i.ytimg.com/vi/{id}/hqdefault.jpg` |
New optional fields to add to `VideoInfo` (useful for judge):
| VideoInfo field | yt-dlp flat field |
|---|---|
| `view_count` | `view_count` |
| `duration` | `duration` (seconds as float) |
| `channel_is_verified` | `channel_is_verified` |
### 2. `src/youtube_types.py` -- Update `VideoInfo`
Add optional fields to `VideoInfo`:
```python
class VideoInfo(_VideoInfoBase, total=False):
    relevance_score: float
    judge_reasoning: str
    view_count: int          # NEW
    duration: float          # NEW (seconds)
    channel_is_verified: bool  # NEW
```
Make `description` and `published_at` optional (move from `_VideoInfoBase` to
`VideoInfo`) since yt-dlp flat mode doesn't provide them.
Remove the Google API-specific types that are no longer needed:
- `ThumbnailInfo`
- `Thumbnails`
- `SearchResultSnippet`
- `VideoId`, `ChannelId`, `PlaylistId`, `ResourceId`
- `SearchResultItem`
- `PageInfo`
- `SearchListResponse`
### 3. `src/judge.py` -- Update judge prompt
The judge currently sends `title`, `channel`, and `description[:300]` to the LLM.
**Change:** Replace `description` with `view_count`, `duration`, and
`channel_is_verified`. These are actually better signals for judging:
- High view count on official channel = almost certainly the real event recording
- Duration of 1-2 hours = full keynote; 5 minutes = likely a recap/reaction
- Verified channel = official source
```python
video_entries.append({
    "index": i,
    "title": v["title"],
    "channel": v["channel_title"],
    "view_count": v.get("view_count"),
    "duration_minutes": round(v.get("duration", 0) / 60, 1),
    "channel_is_verified": v.get("channel_is_verified", False),
})
```
Update the prompt criteria to reference these new fields.
### 4. `src/main.py` -- Update `main()` and `fetch_company_videos()`
- Remove `youtube = build("youtube", "v3", ...)` client initialization.
- Remove `yt_api_key` / `YT_KEY` env var check.
- Remove `youtube` parameter from `fetch_company_videos()`.
- The sort-by-date step needs adjustment since `published_at` won't be
  available. Sort by relevance_score instead, or skip sorting (judge already
  returns at most 1 per year, so order is year-based).
### 5. `pyproject.toml` -- Update dependencies
```diff
 dependencies = [
-    "google-api-python-client>=2.190.0",
-    "google-auth-httplib2>=0.3.0",
-    "google-auth-oauthlib>=1.2.4",
+    "yt-dlp>=2025.1.0",
     "groq>=1.0.0",
     "python-dotenv>=1.2.1",
 ]
```
### 6. `.env` -- Remove `YT_KEY`
No longer needed. Only `GROQ_API_KEY` remains.
## New `search_videos()` Implementation
```python
import yt_dlp
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
            videos.append({
                "video_id": video_id,
                "title": entry.get("title", ""),
                "channel_title": entry.get("channel") or entry.get("uploader") or "",
                "thumbnail_url": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
                "view_count": entry.get("view_count"),
                "duration": entry.get("duration"),
                "channel_is_verified": entry.get("channel_is_verified", False),
            })
        return videos
    except Exception as e:
        print(f"Error searching for '{search_query}' ({year}): {e}")
        return []
```
## Summary of Changes
| File | Action |
|---|---|
| `src/main.py` | Replace `search_videos()`, remove Google API client, fix query bug |
| `src/youtube_types.py` | Add `view_count`/`duration`/`channel_is_verified`, make `description`/`published_at` optional, remove Google API types |
| `src/judge.py` | Update prompt to use view_count + duration + verified instead of description |
| `src/rag.py` | No changes |
| `pyproject.toml` | Swap `google-api-*` deps for `yt-dlp` |
| `.env` | `YT_KEY` no longer needed |
## Risks and Mitigations
| Risk | Mitigation |
|---|---|
| yt-dlp can break if YouTube changes HTML | yt-dlp is actively maintained and updates frequently; pin a minimum version |
| No date filtering in flat mode | Include year in search query -- tested and works well |
| No description for judge | Title + channel + view_count + duration are stronger signals; tested judge quality is comparable |
| Rate limiting from YouTube scraping | yt-dlp handles retries internally; add small delay between searches if needed |
| `published_at` unavailable for sorting | Videos are already 1-per-year-per-event from the judge; natural ordering by year loop is sufficient |
