import os
import json
import subprocess
import tempfile
import math
from typing import Any, List, Tuple, Dict
from concurrent.futures import ThreadPoolExecutor
from groq import Groq
from dotenv import load_dotenv
from groq_retry import groq_call_with_retry

load_dotenv()

# We'll use the same key name as in av_recognition.py
_client = Groq(api_key=os.getenv("OPENAI_API_KEY"))


def _get_duration(path: str) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        path,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return float(res.stdout.strip())


def _extract_chunk(path: str, start: float, duration: float, out_path: str):
    # Re-encode to a lightweight mp3 to ensure we stay under Groq's 25MB limit
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        str(start),
        "-t",
        str(duration),
        "-i",
        path,
        "-vn",
        "-ar",
        "16000",
        "-ac",
        "1",
        "-b:a",
        "64k",
        out_path,
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _transcribe_file(path: str) -> dict:
    with open(path, "rb") as file:
        audio_bytes = file.read()
        transcription = groq_call_with_retry(
            lambda: _client.audio.transcriptions.create(
                file=(path, audio_bytes),
                model="whisper-large-v3-turbo",
                response_format="verbose_json",
                timestamp_granularities=["segment", "word"],
            ),
            op_name="transcribe._transcribe_file",
        )
    return transcription.model_dump()


def _process_chunk(
    start: float, chunk_length: int, audio_path: str
) -> Tuple[float, Dict]:
    """Helper to extract and transcribe a single chunk."""
    # If less than 1sec, just return nothing
    if chunk_length < 1:
        print("Ignoring chunk shorter than 1 sec")
        return start, {}

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_name = tmp.name

    try:
        _extract_chunk(audio_path, start, chunk_length, tmp_name)
        if not os.path.exists(tmp_name) or os.path.getsize(tmp_name) == 0:
            return start, {}

        result = _transcribe_file(tmp_name)
        return start, result
    except Exception as e:
        print(f"Error processing chunk at {start}s: {e}")
        return start, {}
    finally:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)


def transcribe_audio(audio_path: str):
    """
    Transcribes audio using Groq's Whisper-large-v3 model.
    Detects if audio is long or large and chunks it if necessary (Parallelized).
    Returns the verbose_json response including both words segments and timestamps.
    """
    file_size = os.path.getsize(audio_path)
    # Groq limit is 25MB. We'll chunk if > 20MB to be safe, or if it's very long.
    chunk_length = 600  # 10 minutes

    try:
        duration = _get_duration(audio_path)
    except Exception:
        # Fallback to single transcription if ffprobe fails
        return _transcribe_file(audio_path)

    if file_size < 20 * 1024 * 1024 and duration < chunk_length:
        return _transcribe_file(audio_path)

    print(f"Large or long file detected ({duration:.1f}s). Chunking (parallel)...")

    starts = range(0, math.ceil(duration), chunk_length)
    # Using 4-8 threads to avoid overwhelming rate limits while staying fast
    max_workers = 8

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(_process_chunk, start, chunk_length, audio_path)
            for start in starts
        ]
        results = [f.result() for f in futures]

    # Sort results by start time to maintain order
    results.sort(key=lambda x: x[0])

    all_text = []
    all_segments = []
    all_words = []

    for start, result in results:
        if not result:
            continue

        offset = float(start)
        for segment in result.get("segments", []):
            segment["start"] += offset
            segment["end"] += offset
            segment["id"] = len(all_segments)
            all_segments.append(segment)

        for word in result.get("words", []):
            word["start"] += offset
            word["end"] += offset
            all_words.append(word)

        all_text.append(result.get("text", ""))

    return {
        "text": " ".join(all_text),
        "segments": all_segments,
        "words": all_words,
        "duration": duration,
    }


def transcript_to_llm(result: Any) -> str:
    """
    Converts Groq's verbose_json transcription result into a timestamped transcript.
    Format: 00:00 - 00:05 Segment text
    """
    segments = result.get("segments", [])
    lines = []
    for segment in segments:
        start = int(segment.get("start", 0))
        end = int(segment.get("end", 0))
        text = segment.get("text", "").strip()
        if len(text) < 10:
            continue

        start_min = start // 60
        start_sec = start % 60
        end_min = end // 60
        end_sec = end % 60

        lines.append(
            f"{start_min:02d}:{start_sec:02d} - {end_min:02d}:{end_sec:02d} {text}"
        )

    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    from av_recognition import index_face_audio

    # Default test file
    test_file = "./samples/investor_day_short.webm"
    if len(sys.argv) > 1:
        test_file = sys.argv[1]

    if not os.path.exists(test_file):
        print(f"Error: File {test_file} not found.")
        sys.exit(1)

    print(f"Transcribing {test_file}...")
    result = transcribe_audio(test_file)

    print("\nTranscription Text:")
    print(result.get("text", ""))

    print("\nFormatted Transcript for LLM:")
    t = transcript_to_llm(result)
    print(t)

    # Optionally save to a JSON for inspection
    output_json = test_file.rsplit(".", 1)[0] + ".json"
    with open(output_json, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nFull result saved to {output_json}")

    index_face_audio(test_file, t, "Intuit Investor Day", is_audio=True)
