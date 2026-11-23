import html, json, os, re, time
from concurrent.futures import ThreadPoolExecutor
import requests
from flask import Flask, render_template_string, request

TOPICS = {
    "Machine Learning": ["machine learning", "neural network", "deep learning"],
    "Data Structures & Algorithms": ["algorithm", "data structure", "leetcode"],
    "Operating Systems": ["operating system", "kernel", "linux"],
    "Databases": ["database", "sql", "postgres"],
    "Web Development": ["web development", "javascript", "frontend"],
    "Computer Science (general)": ["computer science", "cs50", "programming"],
}

CACHE = "feed.json"
MAX_AGE = 24 * 3600
PAGES = 3
PER_TOPIC = 24

YT = re.compile(r"(?:youtube\.com/watch\?(?:[^\"'\s<]*?(?:&amp;|&))?v=|youtu\.be/)([A-Za-z0-9_-]{11})")


def clean(comment_html):
    text = re.sub(r"<[^>]+>", " ", comment_html or "")
    text = re.sub(r"https?://\S+", "", html.unescape(text))
    return re.sub(r"\s+", " ", text).strip()


def search_comments(keyword):
    for page in range(PAGES):
        r = requests.get(
            "https://hn.algolia.com/api/v1/search",
            params={"query": f"youtube {keyword}", "tags": "comment", "hitsPerPage": 100, "page": page},
            timeout=15,
        )
        r.raise_for_status()
        hits = r.json().get("hits", [])
        if not hits:
            break
        yield from hits


def collect(keywords):
    videos = {}
    for kw in keywords:
        for hit in search_comments(kw):
            raw = hit.get("comment_text") or ""
            ids = set(YT.findall(raw))
            text = clean(raw)
            if not ids or not any(k in text.lower() for k in keywords):
                continue
            when = hit.get("created_at_i", 0)
            for vid in ids:
                v = videos.setdefault(vid, {"id": vid, "count": 0, "last": 0, "quote": "", "hn": "", "_seen": set()})
                if hit["objectID"] in v["_seen"]:
                    continue
                v["_seen"].add(hit["objectID"])
                v["count"] += 1
                if when >= v["last"]:
                    v["last"] = when
                    v["quote"] = text[:220]
                    v["hn"] = "https://news.ycombinator.com/item?id=" + hit["objectID"]
    for v in videos.values():
        v.pop("_seen")
    return list(videos.values())


def enrich(v):
    try:
        r = requests.get("https://www.youtube.com/oembed", timeout=10,
                         params={"url": "https://www.youtube.com/watch?v=" + v["id"], "format": "json"})
        if r.status_code != 200:
            return None
        d = r.json()
        v.update(title=d["title"], channel=d["author_name"],
                 thumb=f"https://i.ytimg.com/vi/{v['id']}/hqdefault.jpg",
                 url="https://www.youtube.com/watch?v=" + v["id"],
                 month=time.strftime("%b %Y", time.gmtime(v["last"])))
        return v
    except Exception:
        return None


def build():
    feed = {"built": time.time(), "topics": {}}
    for topic, keywords in TOPICS.items():
        print("Building:", topic)
        found = sorted(collect(keywords), key=lambda v: (v["count"], v["last"]), reverse=True)
        with ThreadPoolExecutor(8) as pool:
            ready = [v for v in pool.map(enrich, found[: PER_TOPIC * 2]) if v]
        feed["topics"][topic] = ready[:PER_TOPIC]
    json.dump(feed, open(CACHE, "w"))
    return feed


def load():
    if os.path.exists(CACHE):
        feed = json.load(open(CACHE))
        if time.time() - feed["built"] < MAX_AGE:
            return feed
    try:
        return build()
    except Exception as e:
        print("Build failed:", e)
        if os.path.exists(CACHE):
            return json.load(open(CACHE))
        return {"built": 0, "topics": {t: [] for t in TOPICS}}


PAGE = """
<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Student Video Feed</title>
<style>
body{margin:0;font-family:Inter,Arial,sans-serif;background:#f4f6f8;color:#14213d}
header{background:#14213d;color:#fff;padding:20px 32px}
header h1{margin:0;font-size:22px} header p{margin:4px 0 0;color:#c7cfde;font-size:14px}
.bar{display:flex;gap:8px;padding:18px 32px 6px;flex-wrap:wrap}
.bar a{padding:8px 16px;border-radius:999px;background:#fff;border:1px solid #cbd2de;color:#14213d;text-decoration:none;font-size:14px}
.bar a.on{background:#0f766e;color:#fff;border-color:#0f766e}
.sort{padding:0 32px 14px;font-size:14px;color:#4b5568}.sort a{color:#0f766e;margin-left:10px}.sort a.on{font-weight:700;text-decoration:none;color:#14213d}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:18px;padding:0 32px 40px}
.card{background:#fff;border:1px solid #dde2eb;border-radius:12px;overflow:hidden;display:flex;flex-direction:column}
.card img{width:100%;aspect-ratio:16/9;object-fit:cover;display:block;background:#dce4f2}
.body{padding:12px 14px;display:flex;flex-direction:column;gap:6px;flex:1}
.title{font-weight:600;font-size:15px;line-height:1.35;color:#14213d;text-decoration:none}
.meta{color:#4b5568;font-size:13px}.badge{background:#ddf3ef;color:#0b5f58;border-radius:6px;padding:2px 8px;font-size:12px;font-weight:600;align-self:flex-start}
.quote{font-size:13px;color:#2a3550;border-left:3px solid #cbd2de;padding-left:8px}
.links{font-size:12px;margin-top:auto}.links a{color:#0f766e}
.empty{padding:0 32px;color:#4b5568}
</style></head><body>
<header><h1>Student Video Feed</h1><p>Videos people keep recommending in Hacker News comments. No algorithm.</p></header>
<nav class="bar">{% for t in topics %}<a href="/?topic={{ t|urlencode }}&sort={{ sort }}" class="{{ 'on' if t == topic }}">{{ t }}</a>{% endfor %}</nav>
<div class="sort">Sort:
  <a href="/?topic={{ topic|urlencode }}&sort=top" class="{{ 'on' if sort == 'top' }}">Most recommended</a>
  <a href="/?topic={{ topic|urlencode }}&sort=recent" class="{{ 'on' if sort == 'recent' }}">Recently recommended</a></div>
<main class="grid">
{% for v in videos %}
<div class="card"><a href="{{ v.url }}" target="_blank" rel="noopener"><img src="{{ v.thumb }}" alt="" loading="lazy"></a>
<div class="body"><a class="title" href="{{ v.url }}" target="_blank" rel="noopener">{{ v.title }}</a>
<div class="meta">{{ v.channel }}</div>
<span class="badge">Recommended {{ v.count }} time{{ '' if v.count == 1 else 's' }} &middot; last {{ v.month }}</span>
<div class="quote">{{ v.quote }}</div>
<div class="links"><a href="{{ v.hn }}" target="_blank" rel="noopener">See the discussion</a></div></div></div>
{% else %}<p class="empty">No videos yet. Check your internet connection, delete feed.json and run again.</p>{% endfor %}
</main></body></html>
"""

app = Flask(__name__)


@app.route("/")
def home():
    feed = load()
    topics = list(feed["topics"])
    topic = request.args.get("topic", topics[0])
    if topic not in feed["topics"]:
        topic = topics[0]
    sort = request.args.get("sort", "top")
    videos = feed["topics"][topic]
    if sort == "recent":
        videos = sorted(videos, key=lambda v: v["last"], reverse=True)
    return render_template_string(PAGE, topics=topics, topic=topic, sort=sort, videos=videos)


if __name__ == "__main__":
    load()
    app.run(debug=False)