"""Type definitions for YouTube Data API v3 responses."""

from typing import TypedDict, Literal


class ThumbnailInfo(TypedDict):
    """Thumbnail information for a video."""

    url: str
    width: int
    height: int


class Thumbnails(TypedDict, total=False):
    """Collection of thumbnails for a video."""

    default: ThumbnailInfo
    medium: ThumbnailInfo
    high: ThumbnailInfo
    standard: ThumbnailInfo
    maxres: ThumbnailInfo


class SearchResultSnippet(TypedDict):
    """Snippet information for a search result."""

    publishedAt: str
    channelId: str
    title: str
    description: str
    thumbnails: Thumbnails
    channelTitle: str
    liveBroadcastContent: Literal["none", "upcoming", "live"]
    publishTime: str


class VideoId(TypedDict):
    """Video ID information."""

    kind: Literal["youtube#video"]
    videoId: str


class ChannelId(TypedDict):
    """Channel ID information."""

    kind: Literal["youtube#channel"]
    channelId: str


class PlaylistId(TypedDict):
    """Playlist ID information."""

    kind: Literal["youtube#playlist"]
    playlistId: str


# Union type for different resource IDs
ResourceId = VideoId | ChannelId | PlaylistId


class SearchResultItem(TypedDict):
    """Individual search result item."""

    kind: Literal["youtube#searchResult"]
    etag: str
    id: ResourceId
    snippet: SearchResultSnippet


class PageInfo(TypedDict):
    """Pagination information."""

    totalResults: int
    resultsPerPage: int


class SearchListResponse(TypedDict, total=False):
    """Response from YouTube search.list API."""

    kind: Literal["youtube#searchListResponse"]
    etag: str
    nextPageToken: str
    prevPageToken: str
    regionCode: str
    pageInfo: PageInfo
    items: list[SearchResultItem]


class _VideoInfoBase(TypedDict):
    """Required fields for processed video information."""

    video_id: str
    title: str
    description: str
    channel_title: str
    published_at: str  # ISO 8601 format
    thumbnail_url: str


class VideoInfo(_VideoInfoBase, total=False):
    """Processed video information with optional judge metadata."""

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
