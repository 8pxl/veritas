# Put a .json into database
import sys
import json

API = "https://api.totsuki.harvey-l.com/"

video_metadata = sys.argv[1]  # ...json
json_file = sys.argv[2]  # ./demo.json
video_id = sys.argv[3]  # 2ysGbsEnq1Y


# {
#             "video_id": "2ysGbsEnq1Y",
#             "title": "GE Aviation announces Lafayette facility, creating 200 new jobs",
#             "channel_title": "WLFITV",
#             "thumbnail_url": "https://i.ytimg.com/vi/2ysGbsEnq1Y/hqdefault.jpg",
#             "view_count": 138,
#             "duration": 2512.0,
#             "channel_is_verified": null,
#             "relevance_score": 7.5,
#             "judge_reasoning": "Only video 8 has a duration (~42 min) consistent with a press con
# ference and its title indicates a GE Aviation announcement, making it the best candidate.",
#             "upload_date": "2014-03-26"
#           }

# 1. Create video
#
# POST /videos
#
# {
#   "video_id": "string",
#   "video_path": "string",
#   "title": "string",
#   "description": "string",
#   "video_url": "string",
#   "time": "2026-02-22T01:51:51.758Z"
# }
#
#
metadata = {}
for m in json.load(open(video_metadata)):
    if m["video_id"] == video_id:
        print("Found video metadata block")
        requests.post(API)  # TODO


# 2. Create all propositions
#
#
# POST /propositions
# # {
#   "speaker_id": "string",
#   "statement": "string",
#   "video_id": "string"
# }
#
for s in json.load(open(json_file)):
    {
        "speaker_id": s["speaker_alignment"]["speakerId"],
        "statement": s["statement"],
        "video_id": video_id,
    }
