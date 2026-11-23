import os
import re
import sqlite3
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("YOUTUBE_API_KEY")
BASE = "https://www.googleapis.com/youtube/v3"

ML_CHANNELS = [
    "@statquest", "@AndrejKarpathy", "@sentdex", "@Deeplearningai",
    "@YannicKilcher", "@TwoMinutePapers", "@krishnaik06", "@AladdinPersson",
    "@SebastianRaschka", "@campusx-official", "@umarjamilai",
    "@AICoffeeBreak", "@MachineLearningStreetTalk", "@howardjeremyp",
    "@TheAIEpiphany", "@HuggingFace",
]

MIXED_CHANNELS = [
    "@3blue1brown", "@dataschool", "@stanfordonline", "@mitocw",
    "@mreflow", "@matthew_berman", "@WesRoth", "@aiexplained-official",
    "@DwarkeshPatel", "@GoogleDeepMind",
]

ML_PATTERN = re.compile(
    r"\b(?:ai|ml|llm|llms|gpt|rag|nlp)\b|"
    r"\b(?:machine learning|deep learning|neural|transformer|pytorch|tensorflow|"
    r"computer vision|reinforcement|diffusion|attention|gradient|backprop|"
    r"embedding|fine-?tun|scikit|agent|openai|deepseek|llama|gemini|claude|model)",
    re.IGNORECASE,
)

def setup_db():
    conn = sqlite3.connect("feed.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            video_id TEXT PRIMARY KEY, title TEXT, channel TEXT,
            thumbnail TEXT, published_at TEXT, field TEXT,
            views INTEGER, likes INTEGER, score REAL, duration INTEGER
        )
    """)
    return conn

def get_uploads_playlist(handle):
    r = requests.get(f"{BASE}/channels", params={
        "part": "contentDetails", "forHandle": handle, "key": API_KEY,
    }).json()
    items = r.get("items")
    if not items:
        return None
    return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

def get_channel_videos(playlist_id):
    videos, token = [], None
    while True:
        params = {"part": "snippet,contentDetails", "playlistId": playlist_id,
                  "maxResults": 50, "key": API_KEY}
        if token:
            params["pageToken"] = token
        r = requests.get(f"{BASE}/playlistItems", params=params).json()
        if "error" in r:
            print("  API error:", r["error"].get("message"))
            break
        for it in r.get("items", []):
            s = it["snippet"]
            if s["title"] in ("Private video", "Deleted video"):
                continue
            videos.append({
                "id": s["resourceId"]["videoId"],
                "title": s["title"],
                "channel": s.get("videoOwnerChannelTitle", ""),
                "published": it.get("contentDetails", {}).get("videoPublishedAt", s["publishedAt"]),
            })
        token = r.get("nextPageToken")
        if not token:
            break
    return videos

def to_seconds(d):
    m = re.match(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d)
    if not m:
        return 0
    days, h, mi, s = (int(x) if x else 0 for x in m.groups())
    return days * 86400 + h * 3600 + mi * 60 + s

def get_stats(ids):
    out = {}
    for i in range(0, len(ids), 50):
        r = requests.get(f"{BASE}/videos", params={
            "part": "statistics,contentDetails", "id": ",".join(ids[i:i + 50]), "key": API_KEY,
        }).json()
        for v in r.get("items", []):
            st = v.get("statistics", {})
            out[v["id"]] = (int(st.get("viewCount", 0)), int(st.get("likeCount", 0)),
                            to_seconds(v["contentDetails"]["duration"]))
    return out

def make_score(views, likes, published):
    dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
    age_days = (datetime.now(timezone.utc) - dt).days
    return (views + 10 * likes) / (age_days + 2)

if __name__ == "__main__":
    conn = setup_db()
    channels = [(h, False) for h in ML_CHANNELS] + [(h, True) for h in MIXED_CHANNELS]
    for handle, needs_filter in channels:
        playlist = get_uploads_playlist(handle)
        if not playlist:
            print("NOT FOUND:", handle)
            continue
        videos = get_channel_videos(playlist)
        fetched = len(videos)

        off_topic = 0
        if needs_filter:
            kept = [v for v in videos if ML_PATTERN.search(v["title"])]
            off_topic = fetched - len(kept)
            videos = kept

        stats = get_stats([v["id"] for v in videos])
        saved = shorts = unavailable = 0
        for v in videos:
            if v["id"] not in stats:
                unavailable += 1
                continue
            views, likes, secs = stats[v["id"]]
            if secs == 0:  # live streams / premieres with no real length
                unavailable += 1
                continue
            if secs <= 60:
                shorts += 1
            conn.execute(
                "INSERT OR REPLACE INTO videos VALUES (?,?,?,?,?,?,?,?,?,?)",
                (v["id"], v["title"], v["channel"],
                 f"https://i.ytimg.com/vi/{v['id']}/mqdefault.jpg",
                 v["published"], "machine learning", views, likes,
                 make_score(views, likes, v["published"]), secs),
            )
            saved += 1
        conn.commit()
        print(f"{handle}: fetched {fetched} | saved {saved} (shorts {shorts}) | off-topic {off_topic} | unavailable {unavailable}")
    print("Total in database:", conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0])