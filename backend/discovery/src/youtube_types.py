"""Type definitions for YouTube video data (yt-dlp based)."""

from typing import TypedDict


class _VideoInfoBase(TypedDict):
    """Required fields for processed video information."""

    video_id: str
    title: str
    channel_title: str
    thumbnail_url: str


class VideoInfo(_VideoInfoBase, total=False):
    """Processed video information with optional fields."""

    # Fields not available in yt-dlp flat mode
    description: str
    published_at: str  # ISO 8601 format
    upload_date: str  # ISO 8601 date (YYYY-MM-DD), fetched after judge selection

    # Fields from yt-dlp flat mode
    view_count: int
    duration: float  # seconds
    channel_is_verified: bool

    # Judge metadata
    relevance_score: float  # 0-10 relevance score from LLM judge
    judge_reasoning: str  # Explanation of why the video was scored this way


class CompanyEvent(TypedDict):
    """Information about a discovered company event."""

    event_name: str
    search_query: str
    description: str
    frequency: str


class EventVideos(TypedDict):
    """Videos for a specific event with metadata."""

    event_name: str
    search_query: str
    videos: list[VideoInfo]


class CompanyData(TypedDict):
    """Company information and associated videos."""

    symbol: str
    name: str
    events: list[EventVideos]
