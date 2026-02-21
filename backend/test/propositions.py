import cv2
import json
import base64
import os
import subprocess
from dotenv import load_dotenv
from groq import Groq
from groq_retry import groq_call_with_retry

load_dotenv()

EXTRACTION_MODEL = "meta-llama/llama-4-maverick-17b-128e-instruct"
MAX_FRAME_IMAGES = 5

client = Groq(api_key=os.getenv("OPENAI_API_KEY"))

_SYSTEM_PROMPT = """\
You are an analyst extracting verifiable propositions from corporate video transcripts \
(investor days, earnings calls, product launches, keynotes).

A proposition is a clear, self-contained, factual statement made by a company representative \
that can be independently verified. Good examples:
- "Google will release Gemini 3.5 by Q4 2025."
- "Intuit's small business segment revenue grew 18% year-over-year."
- "The new product will be available in 50 countries by end of 2025."

Instructions:
1. Read the transcript carefully. Each line format: MM:SS - MM:SS <spoken text>
2. Use get_frame with timestamps in MM:SS format (for example "06:48") to inspect video frames for additional visual context — slides, charts, \
   on-screen numbers, product names — whenever the transcript alone is ambiguous.
   You can request at most 5 frames total.
3. Extract ALL verifiable propositions made by company representatives.
4. Each proposition must:
   - Be fully self-contained (name the company/product/person explicitly, no dangling pronouns)
   - Represent a single factual claim (split compound claims into separate propositions)
   - Include timestamps matching the transcript segment where it was stated
"""

_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_frame",
            "description": (
                "Grab a frame from the video at a given timestamp. Use this to read "
                "on-screen slides, charts, product names, or numbers that add context "
                "to what the speaker is saying."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "timestamp": {
                        "type": "string",
                        "description": 'Timestamp in MM:SS format, e.g. "06:48".',
                    }
                },
                "required": ["timestamp"],
            },
        },
    }
]


def _timestamp_to_seconds(timestamp: str | float | int) -> float:
    if isinstance(timestamp, (int, float)):
        return float(timestamp)
    raw = str(timestamp).strip()
    parts = raw.split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    return float(raw)


def _grab_frame_b64_ffmpeg(video_path: str, timestamp: float) -> str | None:
    ts = max(0.0, float(timestamp))
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-ss",
        f"{ts:.3f}",
        "-i",
        video_path,
        "-frames:v",
        "1",
        "-vf",
        "scale='min(1280,iw)':-2",
        "-q:v",
        "3",
        "-f",
        "image2pipe",
        "-vcodec",
        "mjpeg",
        "pipe:1",
    ]
    res = subprocess.run(cmd, capture_output=True)
    if res.returncode != 0 or not res.stdout:
        return None
    return base64.b64encode(res.stdout).decode("utf-8")


def _grab_frame_b64_cv2(video_path: str, timestamp: float) -> str | None:
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
    success, frame = cap.read()
    cap.release()
    if not success:
        return None
    frame = cv2.resize(frame, (1280, 720))
    _, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    return base64.b64encode(buffer).decode("utf-8")


def _grab_frame_b64(video_path: str, timestamp: float) -> str | None:
    """Robust frame extraction for AV1/WebM: ffmpeg first, then OpenCV fallback."""
    for offset in (0.0, -0.5, 0.5, -1.0, 1.0):
        b64 = _grab_frame_b64_ffmpeg(video_path, timestamp + offset)
        if b64:
            return b64
    return _grab_frame_b64_cv2(video_path, max(0.0, timestamp))


def _chat_completion_with_retry(
    messages: list[dict],
    tools: list[dict] | None = None,
    response_format: dict | None = None,
    max_retries: int = 5,
):
    kwargs = {
        "model": EXTRACTION_MODEL,
        "messages": messages,
        "temperature": 0,
    }
    if tools is not None:
        kwargs["tools"] = tools
    if response_format is not None:
        kwargs["response_format"] = response_format
    return groq_call_with_retry(
        lambda: client.chat.completions.create(**kwargs),
        max_retries=max_retries,
        retry_tool_use_failed=True,
        op_name="propositions.chat_completion",
    )


def extract_propositions(
    video_path: str,
    transcript: str,
    video_desc: str = "presentation",
    max_turns: int = 20,
) -> list[dict]:
    """
    Extract verifiable propositions from a corporate video transcript.

    Uses a multi-turn tool-use loop so the LLM can inspect video frames for
    visual context (slides, charts, on-screen text) before finalising propositions.

    Args:
        video_path:   Path to the video/audio file.
        transcript:   Formatted transcript string (lines: MM:SS - MM:SS <text>).
        video_desc:   Youtube desc
        max_turns:    Maximum tool-use rounds before forcing the final answer.

    Returns:
        List of dicts: [{"start": "MM:SS", "end": "MM:SS", "statement": "..."}]
    """
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Video Description: {video_desc}\n\n"
                f"Transcript:\n{transcript}\n\n"
                "Use get_frame as needed for visual context, then we will collect all propositions."
            ),
        },
    ]

    # ── Phase 1: multi-turn tool-use loop ────────────────────────────────────
    frame_images_sent = 0
    for _ in range(max_turns):
        response = _chat_completion_with_retry(messages, tools=_TOOLS)
        msg = response.choices[0].message

        if not msg.tool_calls:
            messages.append(msg)
            break

        messages.append(msg)

        # Process all tool calls in this turn
        pending_images: list[tuple[str, str]] = []
        for tc in msg.tool_calls:
            if tc.function.name == "get_frame":
                if frame_images_sent >= MAX_FRAME_IMAGES:
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": (
                                f"Frame budget reached ({MAX_FRAME_IMAGES} max). "
                                "Do not request more frames."
                            ),
                        }
                    )
                    continue
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                ts_raw = args.get("timestamp", "00:00")
                ts_sec = _timestamp_to_seconds(ts_raw)
                print(f"  [frame] {ts_raw} ({ts_sec:.1f}s) ...")
                b64 = _grab_frame_b64(video_path, ts_sec)
                # Tool responses must be text-only per OpenAI spec
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": (
                            f"Frame at {ts_raw} ({ts_sec:.1f}s) grabbed."
                            if b64
                            else f"Could not grab frame at {ts_raw} ({ts_sec:.1f}s)."
                        ),
                    }
                )
                if b64:
                    pending_images.append((str(ts_raw), b64))
                    frame_images_sent += 1

        # Pass grabbed frames back as a user message with inline images
        if pending_images:
            content: list = [{"type": "text", "text": "Requested frames:"}]
            for ts_label, b64 in pending_images:
                content.append({"type": "text", "text": f"t={ts_label}:"})
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                    }
                )
            messages.append({"role": "user", "content": content})

    # ── Phase 2: structured JSON output ──────────────────────────────────────
    messages.append(
        {
            "role": "user",
            "content": (
                "Now output ONLY a JSON object with key 'propositions' containing an array. "
                "Each element must have: start (MM:SS), end (MM:SS), statement (string). "
                "The statement must be self-contained — include company/product names explicitly."
            ),
        }
    )

    final_response = _chat_completion_with_retry(
        messages, response_format={"type": "json_object"}
    )
    content = final_response.choices[0].message.content or "{}"
    try:
        data = json.loads(content)
        return data.get("propositions", [])
    except json.JSONDecodeError:
        print(f"Warning: could not parse JSON:\n{content}")
        return []


if __name__ == "__main__":
    import sys
    from transcribe import transcribe_audio, transcript_to_llm

    test_file = "./samples/investor_day_short.webm"
    if len(sys.argv) > 1:
        test_file = sys.argv[1]

    if not os.path.exists(test_file):
        print(f"Error: File {test_file} not found.")
        sys.exit(1)

    print(f"Transcribing {test_file}...")
    result = transcribe_audio(test_file)
    transcript = transcript_to_llm(result)

    print("\nFormatted Transcript:")
    print(transcript[:500] + ("..." if len(transcript) > 500 else ""))

    print("\nExtracting propositions...")
    propositions = extract_propositions(
        video_path=test_file,
        transcript=transcript,
        video_desc="Intuit",
    )

    print(f"\nFound {len(propositions)} proposition(s):")
    for i, p in enumerate(propositions, 1):
        print(f"\n{i}. [{p.get('start', '?')} - {p.get('end', '?')}]")
        print(f"   {p.get('statement', '')}")
