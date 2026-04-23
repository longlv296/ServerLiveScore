#!/usr/bin/env python3
"""
Fetch football/soccer short videos from YouTube Data API v3.
Saves results to data/short_videos.json for the Android app to consume.

Usage:
    YOUTUBE_API_KEY=xxx python fetch_shorts.py

Security: API key is read from environment variable only — never hardcoded.
"""

import os
import sys
import json
import time
import hashlib
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    print("ERROR: 'requests' package not installed. Run: pip install requests")
    sys.exit(1)

# ── Configuration ──────────────────────────────────────
YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3/search"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "short_videos.json")

# Search queries — rotated to get variety of content
SEARCH_QUERIES = [
    "football shorts",
    "soccer skills",
    "football goals",
    "soccer highlights shorts",
    "best football moments",
    "football tricks",
    "football dribbling skills",
    "premier league highlights shorts",
    "champions league goals shorts",
    "world cup best moments",
    "messi skills shorts",
    "ronaldo goals shorts",
    "neymar tricks shorts",
    "football fails funny",
    "soccer training drills",
]

# How many pages per query (each page = 50 results max = 100 quota units)
PAGES_PER_QUERY = 2
MAX_RESULTS_PER_PAGE = 50

# Target: ~200-500 unique videos per run
# 15 queries × 2 pages × 50 results = 1500 raw → ~500 unique after dedup
# Quota cost: 15 × 2 × 100 = 3000 units (out of 10,000 daily free)


def fetch_videos(api_key: str) -> list[dict]:
    """Fetch videos from YouTube API using multiple search queries."""
    all_videos = {}  # videoId -> video dict (for deduplication)

    for query in SEARCH_QUERIES:
        page_token = None
        for page in range(PAGES_PER_QUERY):
            params = {
                "part": "snippet",
                "q": query,
                "type": "video",
                "videoDuration": "short",
                "videoEmbeddable": "true",
                "videoSyndicated": "true",
                "order": "viewCount",
                "maxResults": MAX_RESULTS_PER_PAGE,
                "relevanceLanguage": "en",
                "safeSearch": "moderate",
                "key": api_key,
            }
            if page_token:
                params["pageToken"] = page_token

            try:
                resp = requests.get(YOUTUBE_API_URL, params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()
            except requests.RequestException as e:
                print(f"  ⚠ Error fetching '{query}' page {page + 1}: {e}")
                break

            items = data.get("items", [])
            for item in items:
                video_id = item.get("id", {}).get("videoId")
                snippet = item.get("snippet", {})
                if not video_id or not snippet:
                    continue

                # Pick best thumbnail
                thumbs = snippet.get("thumbnails", {})
                thumb_url = (
                    (thumbs.get("high") or thumbs.get("medium") or thumbs.get("default") or {}).get("url", "")
                )

                all_videos[video_id] = {
                    "videoId": video_id,
                    "title": snippet.get("title", ""),
                    "channelName": snippet.get("channelTitle", ""),
                    "thumbnailUrl": thumb_url,
                    "publishedAt": snippet.get("publishedAt", ""),
                }

            page_token = data.get("nextPageToken")
            if not page_token:
                break

            # Small delay to be respectful to the API
            time.sleep(0.2)

        count = len(all_videos)
        print(f"  ✓ Query '{query}' done — total unique: {count}")

    return list(all_videos.values())


def save_json(videos: list[dict]) -> str:
    """Save videos to JSON file. Returns the file path."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    output = {
        "updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "totalVideos": len(videos),
        "videos": videos,
    }

    json_str = json.dumps(output, ensure_ascii=False, indent=2)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(json_str)

    return OUTPUT_FILE


def main():
    # ── Security: Read API key from environment only ──
    api_key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not api_key:
        print("ERROR: YOUTUBE_API_KEY environment variable is not set.")
        print("Usage: YOUTUBE_API_KEY=your_key python fetch_shorts.py")
        sys.exit(1)

    # Mask the key in logs for security
    masked_key = api_key[:4] + "***" + api_key[-4:] if len(api_key) > 8 else "***"
    print(f"🔑 Using API key: {masked_key}")
    print(f"🔍 Fetching videos with {len(SEARCH_QUERIES)} queries, {PAGES_PER_QUERY} pages each...")
    print(f"📊 Estimated quota usage: {len(SEARCH_QUERIES) * PAGES_PER_QUERY * 100} units")
    print()

    videos = fetch_videos(api_key)

    if not videos:
        print("⚠ No videos fetched! Check API key and quota.")
        sys.exit(1)

    output_path = save_json(videos)
    print()
    print(f"✅ Saved {len(videos)} unique videos to {output_path}")
    print(f"📁 File size: {os.path.getsize(output_path) / 1024:.1f} KB")


if __name__ == "__main__":
    main()
