#!/usr/bin/env python3
"""
End-to-end automation: download videos, run the analysis pipeline, and push
results to the database.

Usage:
  python automate.py tasks.json
  python automate.py tasks.json --download-dir ./videos --output-dir ./results
  python automate.py tasks.json --skip-download   # reuse already-downloaded files
  python automate.py tasks.json --dry-run
"""

import argparse
import json
import os
import subprocess
import sys


def download_video(video_id: str, download_dir: str) -> str:
    """Download a YouTube video and return the path to the downloaded file."""
    import yt_dlp

    output_template = os.path.join(download_dir, f"{video_id}.%(ext)s")
    ydl_opts = {
        "format": "bestvideo[height<=?720]+bestaudio/best",
        "outtmpl": output_template,
        "quiet": True,
        "no_warnings": True,
    }

    # Use cookies if available
    cookie_file = "./cookies.txt"
    if os.path.exists(cookie_file):
        ydl_opts["cookiefile"] = cookie_file

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(
            f"https://www.youtube.com/watch?v={video_id}", download=True
        )
        return ydl.prepare_filename(info)


def find_downloaded(video_id: str, download_dir: str) -> str | None:
    """Find an already-downloaded file for this video_id."""
    extensions = [".mp4", ".mkv", ".webm", ".mov", ".avi"]
    for ext in extensions:
        path = os.path.join(download_dir, f"{video_id}{ext}")
        if os.path.exists(path):
            return path
    return None


def run_pipeline(video_path: str, description: str, output_path: str) -> int:
    """Run main.py analysis pipeline. Returns the process exit code."""
    cmd = [
        sys.executable,
        "./main.py",
        video_path,
        "--description",
        description,
        "--output",
        output_path,
    ]
    result = subprocess.run(cmd)
    return result.returncode


def push_to_db(pipeline_json: str, tasks_json: str, video_id: str) -> int:
    """Run push_db.py to upload results. Returns the process exit code."""
    cmd = [
        sys.executable,
        "./push_db.py",
        pipeline_json,
        "--video-meta",
        tasks_json,
        "--video-id",
        video_id,
    ]
    result = subprocess.run(cmd)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(
        description="Download, analyze, and push videos to the database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("tasks_json", help="JSON file with list of video task objects")
    parser.add_argument(
        "--download-dir",
        default="./downloads",
        help="Directory for downloaded videos (default: ./downloads)",
    )
    parser.add_argument(
        "--output-dir",
        default="./results",
        help="Directory for pipeline output JSONs (default: ./results)",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip downloading, use existing files in download-dir",
    )
    parser.add_argument(
        "--skip-analysis",
        action="store_true",
        help="Skip analysis, use existing output JSONs in output-dir",
    )
    parser.add_argument(
        "--skip-push", action="store_true", help="Skip pushing to database"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without executing",
    )

    args = parser.parse_args()

    with open(args.tasks_json) as f:
        tasks = json.load(f)

    os.makedirs(args.download_dir, exist_ok=True)
    os.makedirs(args.output_dir, exist_ok=True)

    total = len(tasks)
    succeeded = 0
    failed = []

    for i, task in enumerate(tasks):
        video_id = task["video_id"]
        title = task.get("title", video_id)
        description = title
        output_path = os.path.join(args.output_dir, f"{video_id}.json")

        print(f"\n{'=' * 60}")
        print(f"[{i + 1}/{total}] {video_id} - {title}")
        print(f"{'=' * 60}")

        # Step 1: Download
        video_path = find_downloaded(video_id, args.download_dir)
        if args.skip_download or args.skip_analysis:
            if video_path:
                print(f"  Using existing: {video_path}")
            elif not args.skip_analysis:
                print(f"  No existing download found for {video_id}, downloading...")
        if not video_path and not args.skip_analysis:
            if args.dry_run:
                print(f"  [dry-run] Would download {video_id}")
                video_path = os.path.join(args.download_dir, f"{video_id}.mp4")
            else:
                print(f"  Downloading {video_id}...")
                try:
                    video_path = download_video(video_id, args.download_dir)
                    print(f"  Downloaded: {video_path}")
                except Exception as e:
                    print(f"  Download failed: {e}", file=sys.stderr)
                    failed.append((video_id, f"download: {e}"))
                    continue

        # Step 2: Analyze
        if os.path.exists(output_path) and not args.skip_analysis:
            print(f"  Analysis already exists: {output_path}, skipping")
        elif not args.skip_analysis:
            if args.dry_run:
                print(f"  [dry-run] Would analyze {video_path} -> {output_path}")
            else:
                print(f"  Analyzing {video_path}...")
                rc = run_pipeline(video_path, description, output_path)
                if rc != 0:
                    print(f"  Analysis failed (exit code {rc})", file=sys.stderr)
                    failed.append((video_id, f"analysis: exit code {rc}"))
                    continue
                print(f"  Analysis output: {output_path}")

                print(f"  Pushing to database...")
                rc = push_to_db(output_path, args.tasks_json, video_id)
                if rc != 0:
                    print(f"  Push failed (exit code {rc})", file=sys.stderr)
                    failed.append((video_id, f"push: exit code {rc}"))
                    continue
                print(f"  Push complete.")
        else:
            if not os.path.exists(output_path):
                print(
                    f"  No analysis output found at {output_path}, skipping",
                    file=sys.stderr,
                )
                failed.append((video_id, "analysis output not found"))
                continue
            print(f"  Using existing analysis: {output_path}")

        succeeded += 1

    print(f"\n{'=' * 60}")
    print(f"Finished: {succeeded}/{total} succeeded")
    if failed:
        print(f"Failed ({len(failed)}):")
        for vid, reason in failed:
            print(f"  {vid}: {reason}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
