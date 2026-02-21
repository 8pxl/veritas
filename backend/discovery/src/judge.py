import json
from groq import Groq
from youtube_types import VideoInfo


def judge_videos_batch(
    groq_client: Groq,
    videos: list[VideoInfo],
    event_name: str,
    company_name: str,
) -> VideoInfo | None:
    """
    Judge a batch of videos and return the single best match, or None.

    Sends titles, channels, and descriptions to an LLM which picks at most
    one video that is a genuine, primary-source recording of the event.
    Returns None when no video in the batch is relevant.
    """
    if not videos:
        return None

    video_entries = []
    for i, v in enumerate(videos):
        video_entries.append(
            {
                "index": i,
                "title": v["title"],
                "channel": v["channel_title"],
                "description": v["description"][:300],
            }
        )

    prompt = f"""You are a strict video relevance judge. You must decide which (if any) of the following YouTube videos is a genuine, primary-source recording of the event "{event_name}" by or about "{company_name}".

Videos:
{json.dumps(video_entries, indent=2)}

RULES — read carefully:

1. Pick AT MOST ONE video — the single best match.
2. If NONE of the videos are a genuine recording of the event, return {{"chosen_index": -1}}.
   Do NOT be afraid to return -1. Some searches will not have a relevant result.
3. The video MUST be an actual recording where company leaders (CEO, CTO, executives)
   are speaking, OR an official recording of the event itself.
4. DO NOT pick:
   - Third-party commentary, reactions, or recap videos
   - News segments that merely discuss the event
   - Stock/trading analysis referencing the event
   - Tutorials or educational content
   - Compilations or highlight reels made by fans
   - Videos about a different company or event
5. Prefer official company channels, but accept reputable media uploads of the
   actual event footage (e.g. Bloomberg uploading a full keynote).

Return ONLY this JSON (no other text):
{{
  "chosen_index": <integer>,
  "relevance_score": <float 0-10>,
  "reasoning": "<one sentence>"
}}"""

    try:
        resp = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an extremely strict video relevance judge. "
                        "You output only valid JSON. "
                        "You frequently return null when nothing matches. "
                        "Quality over quantity."
                    ),
                },
                {"role": "user", "content": prompt},
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
