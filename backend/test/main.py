import argparse
import json
import os
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from transcribe import transcribe_audio, transcript_to_llm


def _ts_to_sec(ts: str | float | int) -> float:
    if isinstance(ts, (float, int)):
        return float(ts)
    parts = str(ts).strip().split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return float(parts[0]) if parts and parts[0] else 0.0


def _has_video_stream(path: str) -> bool:
    res = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        capture_output=True,
        text=True,
    )
    return "video" in (res.stdout or "").lower()


def _extract_audio_clip(input_path: str, start_s: float, end_s: float) -> str:
    duration = max(0.75, end_s - start_s)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        out_path = tmp.name
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        str(max(0.0, start_s)),
        "-t",
        str(duration),
        "-i",
        input_path,
        "-vn",
        "-ar",
        "16000",
        "-ac",
        "1",
        out_path,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        os.unlink(out_path)
        raise RuntimeError(f"ffmpeg audio clip failed: {res.stderr[-300:]}")
    return out_path


def _extract_video_clip(input_path: str, start_s: float, end_s: float) -> str:
    duration = max(0.75, end_s - start_s)
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        out_path = tmp.name
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        str(max(0.0, start_s)),
        "-t",
        str(duration),
        "-i",
        input_path,
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "28",
        out_path,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        os.unlink(out_path)
        raise RuntimeError(f"ffmpeg video clip failed: {res.stderr[-300:]}")
    return out_path


def _overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def _match_speaker(statement: dict, speaker_segments: list[dict]) -> dict[str, Any]:
    s0 = _ts_to_sec(statement.get("start", 0))
    s1 = _ts_to_sec(statement.get("end", s0))
    if s1 < s0:
        s0, s1 = s1, s0
    best_seg = None
    best_overlap = 0.0
    for seg in speaker_segments:
        g0 = _ts_to_sec(seg.get("start", 0))
        g1 = _ts_to_sec(seg.get("end", g0))
        ov = _overlap(s0, s1, g0, g1)
        if ov > best_overlap:
            best_overlap = ov
            best_seg = seg
    if best_seg:
        return {
            "speakerId": best_seg.get("speakerId"),
            "segment_start": best_seg.get("start"),
            "segment_end": best_seg.get("end"),
            "overlap_seconds": round(best_overlap, 3),
        }
    return {
        "speakerId": None,
        "segment_start": None,
        "segment_end": None,
        "overlap_seconds": 0.0,
    }


def _analyze_statement(
    input_path: str, statement: dict, speaker_segments: list[dict], has_video: bool
) -> dict:
    start_raw = statement.get("start", "00:00")
    end_raw = statement.get("end", start_raw)
    start_s = _ts_to_sec(start_raw)
    end_s = _ts_to_sec(end_raw)
    if end_s < start_s:
        start_s, end_s = end_s, start_s

    speaker_alignment = _match_speaker(statement, speaker_segments)
    speaker_info = {}
    if speaker_alignment.get("speakerId"):
        from av_recognition import _lookup_speaker

        speaker_info = _lookup_speaker(speaker_alignment["speakerId"]) or {}

    audio_result: dict[str, Any]
    facial_result: dict[str, Any]
    audio_tmp = None
    video_tmp = None
    try:
        from audio_analysis import compute_confidence_score

        audio_tmp = _extract_audio_clip(input_path, start_s, end_s)
        audio_result = compute_confidence_score(audio_tmp)
    except (ImportError, RuntimeError, OSError, ValueError) as e:
        audio_result = {"confidence_score": 0.0, "error": str(e)}
    finally:
        if audio_tmp and os.path.exists(audio_tmp):
            os.unlink(audio_tmp)

    if has_video:
        try:
            from video_analysis import compute_facial_confidence

            video_tmp = _extract_video_clip(input_path, start_s, end_s)
            facial_result = compute_facial_confidence(video_tmp, fps=2)
        except (ImportError, RuntimeError, OSError, ValueError) as e:
            facial_result = {"confidence_score": 0.0, "error": str(e)}
        finally:
            if video_tmp and os.path.exists(video_tmp):
                os.unlink(video_tmp)
    else:
        facial_result = {
            "confidence_score": None,
            "error": "Input is audio-only; facial confidence unavailable.",
        }

    return {
        "start": statement.get("start"),
        "end": statement.get("end"),
        "statement": statement.get("statement") or statement.get("proposition", ""),
        "speaker_alignment": speaker_alignment,
        "speaker_info": speaker_info,
        "audio_confidence": audio_result,
        "facial_confidence": facial_result,
    }


def run_pipeline(input_path: str, description: str = "") -> dict:
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    print("Step 1/4: Transcribing...")
    transcription = transcribe_audio(input_path)
    transcript_text = transcript_to_llm(transcription)

    print("Step 2/4: Running indexing + proposition extraction in parallel...")
    has_video = _has_video_stream(input_path)
    from av_recognition import index_face_audio
    from propositions import extract_propositions

    with ThreadPoolExecutor(max_workers=2) as pool:
        index_future = pool.submit(
            index_face_audio,
            input_path,
            transcript_text,
            description or os.path.basename(input_path),
            not has_video,
        )
        props_future = pool.submit(
            extract_propositions,
            input_path,
            transcript_text,
            description,
        )
        speaker_segments = index_future.result()
        propositions = props_future.result()

    print("Step 3/4: Scoring each statement...")
    statement_analyses = [
        _analyze_statement(input_path, statement, speaker_segments, has_video)
        for statement in propositions
    ]

    print("Step 4/4: Building output JSON...")
    return {
        "input_file": input_path,
        "description": description,
        "has_video_stream": has_video,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "transcription_raw": transcription,
        "transcript_for_llm": transcript_text,
        "speaker_segments": speaker_segments,
        "propositions": propositions,
        "statement_analyses": statement_analyses,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run full speech + proposition confidence pipeline."
    )
    parser.add_argument("input_file", help="Path to input video/audio file")
    parser.add_argument(
        "--description",
        default="",
        help="Optional event description for speaker indexing",
    )
    parser.add_argument("--output", default="", help="Output JSON path")
    args = parser.parse_args()

    result = run_pipeline(args.input_file, description=args.description)
    output_path = args.output or f"{os.path.splitext(args.input_file)[0]}_pipeline.json"
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"Done. Full pipeline output saved to {output_path}")
