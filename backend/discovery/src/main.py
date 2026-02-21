import os
from typing import cast
from dotenv import load_dotenv
from googleapiclient.discovery import build
from youtube_types import SearchListResponse
import json


def main():
    env = load_dotenv()
    if not env:
        print("failed to load dot env!")
        exit()
    yt = build("youtube", "v3", developerKey=os.getenv("YT_KEY"))

    request = yt.search().list(
        part="snippet", q="robotics tutorial", type="video", maxResults=5
    )
    res: SearchListResponse = cast(SearchListResponse, request.execute())


if __name__ == "__main__":
    main()
