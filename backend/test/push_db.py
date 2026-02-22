#!/usr/bin/env python3
"""Push pipeline output (video + propositions) into the database API."""

import argparse
import json
import sys
from datetime import datetime, timezone

import requests

DEFAULT_API = "https://api.totsuki.harvey-l.com"


def create_video(api: str, video_id: str, title: str, description: str,
                 video_url: str, video_path: str, time: str) -> dict:
    payload = {
        "video_id": video_id,
        "video_path": video_path,
        "title": title,
        "description": description,
        "video_url": video_url,
        "time": time,
    }
    resp = requests.post(f"{api}/videos", json=payload)
    resp.raise_for_status()
    return resp.json()


def create_proposition(api: str, speaker_id: str, statement: str,
                       video_id: str, verify_at: str) -> dict:
    payload = {
        "speaker_id": speaker_id,
        "statement": statement,
        "video_id": video_id,
        "verify_at": verify_at,
    }
    resp = requests.post(f"{api}/propositions", json=payload)
    resp.raise_for_status()
    return resp.json()


def main():
    parser = argparse.ArgumentParser(
        description="Push pipeline JSON output into the database API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  %(prog)s demo.json --video-id 2ysGbsEnq1Y --title "Intuit Investor Day"
  %(prog)s demo.json --video-id abc123 --video-meta metadata.json
  %(prog)s demo.json --video-id abc123 --title "My Video" --dry-run
""",
    )
    parser.add_argument("pipeline_json",
                        help="Pipeline output JSON file (from main.py)")
    parser.add_argument("--video-id", required=True,
                        help="YouTube video ID")
    parser.add_argument("--title",
                        help="Video title (or pulled from --video-meta)")
    parser.add_argument("--video-meta",
                        help="JSON file with video metadata array "
                             "(searches for matching video_id)")
    parser.add_argument("--video-url",
                        help="Video URL (default: YouTube URL from video-id)")
    parser.add_argument("--video-path", default="",
                        help="Video file path stored in DB (default: empty)")
    parser.add_argument("--api", default=DEFAULT_API,
                        help=f"API base URL (default: {DEFAULT_API})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be sent without making requests")

    args = parser.parse_args()

    # Load pipeline JSON
    with open(args.pipeline_json) as f:
        pipeline = json.load(f)

    # Resolve video metadata
    title = args.title or pipeline.get("description", "")
    description = pipeline.get("description", "")
    video_url = args.video_url or f"https://www.youtube.com/watch?v={args.video_id}"
    now = datetime.now(timezone.utc).isoformat()

    # If --video-meta is provided, try to find the matching entry
    if args.video_meta:
        with open(args.video_meta) as f:
            meta_list = json.load(f)
        if not isinstance(meta_list, list):
            meta_list = [meta_list]
        for m in meta_list:
            if m.get("video_id") == args.video_id:
                title = title or m.get("title", "")
                if m.get("channel_title"):
                    description = description or f"{m['channel_title']} - {m.get('title', '')}"
                if m.get("upload_date"):
                    now = m["upload_date"] + "T00:00:00+00:00"
                if not args.video_url and m.get("thumbnail_url"):
                    video_url = f"https://www.youtube.com/watch?v={args.video_id}"
                print(f"Found video metadata for {args.video_id}: {m.get('title')}")
                break
        else:
            print(f"Warning: video_id {args.video_id} not found in {args.video_meta}",
                  file=sys.stderr)

    if not title:
        print("Error: --title is required (or provide --video-meta)", file=sys.stderr)
        sys.exit(1)

    # Step 1: Create video
    print(f"Creating video: {args.video_id} - {title}")
    if args.dry_run:
        print(f"  [dry-run] POST /videos")
        print(f"    video_id:   {args.video_id}")
        print(f"    title:      {title}")
        print(f"    video_url:  {video_url}")
        print(f"    time:       {now}")
    else:
        try:
            result = create_video(
                args.api, args.video_id, title, description,
                video_url, args.video_path, now,
            )
            print(f"  Created video: {result.get('video_id')}")
        except requests.HTTPError as e:
            print(f"  Error creating video: {e}", file=sys.stderr)
            print(f"  Response: {e.response.text}", file=sys.stderr)
            sys.exit(1)

    # Step 2: Create propositions from statement_analyses
    analyses = pipeline.get("statement_analyses", [])
    if not analyses:
        print("No statement_analyses found in pipeline JSON.")
        return

    created = 0
    skipped = 0
    errors = 0

    for i, s in enumerate(analyses):
        speaker_id = (s.get("speaker_alignment") or {}).get("speakerId")
        statement = s.get("statement", "")

        if not speaker_id:
            skipped += 1
            if not args.dry_run:
                print(f"  [{i+1}/{len(analyses)}] Skipped (no speaker): {statement[:60]}")
            continue

        if not statement.strip():
            skipped += 1
            continue

        if args.dry_run:
            print(f"  [{i+1}/{len(analyses)}] [dry-run] POST /propositions")
            print(f"    speaker_id: {speaker_id}")
            print(f"    statement:  {statement[:80]}")
            created += 1
            continue

        try:
            result = create_proposition(
                args.api, speaker_id, statement, args.video_id, now,
            )
            created += 1
            print(f"  [{i+1}/{len(analyses)}] Created proposition #{result.get('id')}: "
                  f"{statement[:60]}")
        except requests.HTTPError as e:
            errors += 1
            print(f"  [{i+1}/{len(analyses)}] Error: {e} - {statement[:60]}",
                  file=sys.stderr)

    print(f"\nDone. {created} created, {skipped} skipped, {errors} errors "
          f"(out of {len(analyses)} total)")


if __name__ == "__main__":
    main()
