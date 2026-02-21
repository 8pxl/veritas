"""Download YouTube videos from the discovery output JSON using yt-dlp + ffmpeg.

Usage:
    python downloader.py [path/to/sp500_youtube_videos_groq.json]

Videos are saved to  out/media/<SYMBOL>/<video_id>.mp4
Supports graceful Ctrl+C (finishes current download, then stops) and
automatic resume (skips videos that already exist on disk).
"""

import json
import os
import signal
import sys

import yt_dlp

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_INPUT = "out/sp500_youtube_videos_groq.json"
MEDIA_ROOT = "out/media"

# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------

_stop_requested = False


def _signal_handler(sig, frame):
    global _stop_requested
    if _stop_requested:
        print("\nForce quit.")
        sys.exit(1)
    _stop_requested = True
    print("\nStop requested — will exit after the current download finishes.")
    print("Press Ctrl+C again to force quit.")


# ---------------------------------------------------------------------------
# Downloader
# ---------------------------------------------------------------------------


def download_video(video_id: str, out_dir: str) -> bool:
    """Download a single YouTube video into *out_dir* as <video_id>.mp4.

    Returns True if the file exists on disk after the call (downloaded or
    already present), False on failure.
    """
    out_path = os.path.join(out_dir, f"{video_id}.mp4")

    if os.path.exists(out_path):
        return True  # already downloaded

    os.makedirs(out_dir, exist_ok=True)

    ydl_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "outtmpl": os.path.join(out_dir, "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
        return os.path.exists(out_path)
    except Exception as e:
        print(f"      Error downloading {video_id}: {e}")
        return False


def main():
    input_file = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_INPUT

    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found")
        sys.exit(1)

    with open(input_file, "r", encoding="utf-8") as f:
        companies = json.load(f)

    # Collect all (symbol, video_id) pairs
    tasks: list[tuple[str, str, str]] = []  # (symbol, video_id, title)
    for company in companies:
        symbol = company["symbol"]
        for event in company.get("events", []):
            for video in event.get("videos", []):
                vid = video.get("video_id")
                if vid:
                    tasks.append((symbol, vid, video.get("title", vid)))

    if not tasks:
        print("No videos to download.")
        return

    # Count how many are already downloaded
    already = sum(
        1
        for sym, vid, _ in tasks
        if os.path.exists(os.path.join(MEDIA_ROOT, sym, f"{vid}.mp4"))
    )

    print(f"Found {len(tasks)} videos across {len(companies)} companies")
    if already:
        print(f"  {already} already downloaded, {len(tasks) - already} remaining")
    print(f"Downloading to {MEDIA_ROOT}/<SYMBOL>/<video_id>.mp4")
    print("(Press Ctrl+C to stop after the current download)\n")

    # Install signal handler
    original_sigint = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, _signal_handler)

    downloaded = 0
    skipped = 0
    failed = 0

    for i, (symbol, video_id, title) in enumerate(tasks, 1):
        if _stop_requested:
            print(f"\nStopping at video {i}/{len(tasks)}.")
            break

        out_dir = os.path.join(MEDIA_ROOT, symbol)
        out_path = os.path.join(out_dir, f"{video_id}.mp4")

        if os.path.exists(out_path):
            skipped += 1
            continue

        short_title = title[:60] + "..." if len(title) > 60 else title
        print(f"[{i}/{len(tasks)}] {symbol} | {short_title}")

        ok = download_video(video_id, out_dir)
        if ok:
            downloaded += 1
            print(f"         -> saved to {out_path}")
        else:
            failed += 1

    # Restore signal handler
    signal.signal(signal.SIGINT, original_sigint)

    print(f"\n{'=' * 60}")
    print(f"Done.  Downloaded: {downloaded}  Skipped: {skipped}  Failed: {failed}")
    if _stop_requested:
        print("Run again to resume.")


if __name__ == "__main__":
    main()
