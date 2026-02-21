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


def _sec_to_mmss(sec: float) -> str:
    value = max(0, int(sec))
    return f"{value // 60:02d}:{value % 60:02d}"


def _segments_to_transcript(segments: list[dict]) -> str:
    lines = []
    for segment in segments:
        start = _sec_to_mmss(float(segment.get("start", 0)))
        end = _sec_to_mmss(float(segment.get("end", 0)))
        text = str(segment.get("text", "")).strip()
        lines.append(f"{start} - {end} {text}")
    return "\n".join(lines)


def _chunk_transcript_segments(
    segments: list[dict], chunk_seconds: int = 1200
) -> list[dict[str, Any]]:
    if not segments:
        return []
    sorted_segments = sorted(segments, key=lambda s: float(s.get("start", 0)))
    chunks: list[dict[str, Any]] = []
    current: list[dict] = []
    chunk_start = float(sorted_segments[0].get("start", 0))
    for seg in sorted_segments:
        seg_start = float(seg.get("start", 0))
        seg_end = float(seg.get("end", seg_start))
        if current and seg_end - chunk_start > chunk_seconds:
            chunks.append(
                {
                    "start_sec": chunk_start,
                    "end_sec": float(current[-1].get("end", chunk_start)),
                    "transcript": _segments_to_transcript(current),
                }
            )
            current = []
            chunk_start = seg_start
        current.append(seg)
    if current:
        chunks.append(
            {
                "start_sec": chunk_start,
                "end_sec": float(current[-1].get("end", chunk_start)),
                "transcript": _segments_to_transcript(current),
            }
        )
    return chunks


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
        "-acodec",
        "pcm_s16le",
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


def _match_speaker_by_overlap(
    statement: dict, speaker_segments: list[dict]
) -> dict[str, Any]:
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
            "match_method": "segment_overlap_fallback",
        }
    return {
        "speakerId": None,
        "segment_start": None,
        "segment_end": None,
        "overlap_seconds": 0.0,
        "match_method": "segment_overlap_fallback",
    }


def _match_speaker(
    statement: dict, speaker_segments: list[dict], audio_clip_path: str | None
) -> dict[str, Any]:
    if audio_clip_path:
        from av_recognition import find_audio

        matches = find_audio(audio_clip_path)
        best_match = next(
            (
                m
                for m in matches
                if isinstance(m, dict) and not m.get("error") and m.get("speakerId")
            ),
            None,
        )
        if best_match:
            return {
                "speakerId": best_match.get("speakerId"),
                "segment_start": best_match.get("start"),
                "segment_end": best_match.get("end"),
                "vector_distance": best_match.get("distance"),
                "vector_time": best_match.get("time"),
                "match_method": "voice_fingerprint_vector_db",
            }
    return _match_speaker_by_overlap(statement, speaker_segments)


def _process_step2_chunk(
    input_path: str, chunk_transcript: str, chunk_desc: str, is_audio: bool
) -> tuple[list[dict], list[dict]]:
    from av_recognition import index_face_audio
    from propositions import extract_propositions

    with ThreadPoolExecutor(max_workers=2) as pool:
        index_future = pool.submit(
            index_face_audio,
            input_path,
            chunk_transcript,
            chunk_desc,
            is_audio,
        )
        props_future = pool.submit(
            extract_propositions,
            input_path,
            chunk_transcript,
            chunk_desc,
        )
        return index_future.result(), props_future.result()


def _analyze_statement(
    input_path: str, statement: dict, speaker_segments: list[dict], has_video: bool
) -> dict:
    start_raw = statement.get("start", "00:00")
    end_raw = statement.get("end", start_raw)
    start_s = _ts_to_sec(start_raw)
    end_s = _ts_to_sec(end_raw)
    if end_s < start_s:
        start_s, end_s = end_s, start_s

    speaker_alignment = _match_speaker_by_overlap(statement, speaker_segments)
    speaker_info = {}

    audio_result: dict[str, Any]
    facial_result: dict[str, Any]
    audio_tmp = None
    video_tmp = None
    try:
        from audio_analysis import compute_confidence_score

        audio_tmp = _extract_audio_clip(input_path, start_s, end_s)
        try:
            speaker_alignment = _match_speaker(statement, speaker_segments, audio_tmp)
        except (ImportError, RuntimeError, OSError, ValueError) as e:
            speaker_alignment["vector_match_error"] = str(e)
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

    if speaker_alignment.get("speakerId"):
        from av_recognition import _lookup_speaker

        speaker_info = _lookup_speaker(speaker_alignment["speakerId"]) or {}

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
    chunked_transcripts = _chunk_transcript_segments(
        transcription.get("segments", []), chunk_seconds=1200
    )
    if not chunked_transcripts:
        chunked_transcripts = [
            {
                "start_sec": 0.0,
                "end_sec": 0.0,
                "transcript": transcript_text,
            }
        ]

    print("Step 2/4: Running chunked indexing + proposition extraction in parallel...")
    has_video = _has_video_stream(input_path)
    is_audio_only = not has_video
    max_workers = min(3, max(1, len(chunked_transcripts)))
    speaker_segments_all: list[dict] = []
    propositions_all: list[dict] = []
    chunk_meta: list[dict] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = []
        for idx, chunk in enumerate(chunked_transcripts):
            chunk_desc = (
                f"{description or os.path.basename(input_path)} | "
                f"chunk {idx + 1}/{len(chunked_transcripts)} "
                f"({_sec_to_mmss(chunk['start_sec'])}-{_sec_to_mmss(chunk['end_sec'])})"
            )
            futures.append(
                (
                    idx,
                    chunk,
                    pool.submit(
                        _process_step2_chunk,
                        input_path,
                        chunk["transcript"],
                        chunk_desc,
                        is_audio_only,
                    ),
                )
            )

        for idx, chunk, future in futures:
            chunk_speakers, chunk_props = future.result()
            speaker_segments_all.extend(chunk_speakers or [])
            propositions_all.extend(chunk_props or [])
            chunk_meta.append(
                {
                    "chunk_index": idx,
                    "start_sec": chunk["start_sec"],
                    "end_sec": chunk["end_sec"],
                    "speaker_segments_count": len(chunk_speakers or []),
                    "propositions_count": len(chunk_props or []),
                }
            )

    speaker_seen: set[tuple] = set()
    speaker_segments: list[dict] = []
    for seg in speaker_segments_all:
        key = (seg.get("speakerId"), seg.get("start"), seg.get("end"))
        if key in speaker_seen:
            continue
        speaker_seen.add(key)
        speaker_segments.append(seg)
    speaker_segments.sort(key=lambda s: _ts_to_sec(s.get("start", 0)))

    prop_seen: set[tuple] = set()
    propositions: list[dict] = []
    for p in propositions_all:
        statement = p.get("statement") or p.get("proposition") or ""
        key = (p.get("start"), p.get("end"), statement.strip())
        if key in prop_seen:
            continue
        prop_seen.add(key)
        propositions.append(p)
    propositions.sort(key=lambda p: _ts_to_sec(p.get("start", 0)))

    print("Step 3/4: Scoring each statement...")
    analysis_workers = min(8, max(1, len(propositions)))
    with ThreadPoolExecutor(max_workers=analysis_workers) as pool:
        statement_analyses = list(
            pool.map(
                lambda statement: _analyze_statement(
                    input_path, statement, speaker_segments, has_video
                ),
                propositions,
            )
        )

    print("Step 4/4: Building output JSON...")
    return {
        "input_file": input_path,
        "description": description,
        "has_video_stream": has_video,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "transcription_raw": transcription,
        "transcript_for_llm": transcript_text,
        "step2_chunking": {
            "chunk_seconds": 1200,
            "chunk_count": len(chunked_transcripts),
            "chunks": chunk_meta,
        },
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
