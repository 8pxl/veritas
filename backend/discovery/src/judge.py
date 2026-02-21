"""LLM-based video relevance judge using Groq."""

import json
from groq import Groq
from youtube_types import VideoInfo
from prompts import load_prompt


def judge_videos_batch(
    groq_client: Groq,
    videos: list[VideoInfo],
    event_name: str,
    company_name: str,
) -> VideoInfo | None:
    """
    Judge a batch of videos and return the single best match, or None.

    Sends titles, channels, and yt-dlp metadata to an LLM which picks at most
    one video that is a genuine, primary-source recording of the event.
    Returns None when no video in the batch is relevant.
    """
    if not videos:
        return None

    video_entries = []
    for i, v in enumerate(videos):
        duration_sec = v.get("duration")
        duration_min = round(duration_sec / 60, 1) if duration_sec else None

        video_entries.append(
            {
                "index": i,
                "title": v["title"],
                "channel": v["channel_title"],
                "view_count": v.get("view_count"),
                "duration_minutes": duration_min,
                "channel_is_verified": v.get("channel_is_verified", False),
            }
        )

    video_entries_json = json.dumps(video_entries, indent=2)

    system_prompt = load_prompt("judge_system")
    user_prompt = load_prompt("judge_user").format(
        event_name=event_name,
        company_name=company_name,
        video_entries_json=video_entries_json,
    )

    try:
        resp = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model="openai/gpt-oss-120b",
            temperature=0,
            max_tokens=256,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "yt_res",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "chosen_index": {"type": "integer"},
                            "relevance_score": {"type": "number"},
                            "reasoning": {"type": "string"},
                        },
                        "required": ["chosen_index"],
                        "additionalProperties": False,
                    },
                },
            },
        )

        response_text = (resp.choices[0].message.content or "").strip()

        # Strip markdown fences if present
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1])

        judgment = json.loads(response_text)

    except (json.JSONDecodeError, Exception) as e:
        print(f"    Judge error: {e}")
        return None

    chosen = judgment.get("chosen_index")

    chosen = int(chosen)
    if chosen < 0 or chosen >= len(videos):
        return None

    video = videos[chosen]
    video["relevance_score"] = float(judgment.get("relevance_score", 0))
    video["judge_reasoning"] = judgment.get("reasoning", "")
    return video


def deduplicate_videos(videos: list[VideoInfo]) -> list[VideoInfo]:
    """
    Remove duplicate video_ids, keeping the entry with the highest
    relevance_score.
    """
    best: dict[str, VideoInfo] = {}
    for v in videos:
        vid = v["video_id"]
        existing = best.get(vid)
        if existing is None or v.get("relevance_score", 0) > existing.get(
            "relevance_score", 0
        ):
            best[vid] = v
    return list(best.values())
