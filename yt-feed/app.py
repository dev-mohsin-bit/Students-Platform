import math
import random
import re
import sqlite3
import time
from difflib import get_close_matches
from flask import Flask, render_template, request, jsonify
from topics import TAXONOMY

app = Flask(__name__)
PER_PAGE = 24

TABS = {
    "shorts": (0, 61), "videos": (61, 10**9), "u5": (61, 300), "5-10": (300, 600),
    "10-30": (600, 1800), "30-60": (1800, 3600), "60plus": (3600, 10**9),
}
LIBRARY = {"history": "history", "liked": "likes", "later": "watch_later"}

def feed_db():
    conn = sqlite3.connect("feed.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_user_db():
    conn = sqlite3.connect("user.db")
    for table in ("history", "likes", "watch_later"):
        conn.execute(f"CREATE TABLE IF NOT EXISTS {table} "
                     "(uid TEXT, video_id TEXT, ts REAL, PRIMARY KEY (uid, video_id))")
    conn.commit()
    conn.close()

def user_db():
    return sqlite3.connect("user.db")

init_user_db()
cache = {}

# ----- typo-tolerant search -----
_vocab = None
_fuzzy_cache = {}

def get_vocab():
    global _vocab
    if _vocab is None:
        conn = feed_db()
        words = set()
        for title, channel in conn.execute("SELECT title, channel FROM videos"):
            words.update(re.findall(r"[a-z0-9]+", (title + " " + channel).lower()))
        conn.close()
        _vocab = sorted(w for w in words if len(w) >= 3)
    return _vocab

def expand_word(word):
    """Words to search for: the typed word if it matches something, else its closest spellings."""
    if word in _fuzzy_cache:
        return _fuzzy_cache[word]
    vocab = get_vocab()
    if len(word) < 4 or any(word in w for w in vocab):
        result = [word]
    else:
        result = get_close_matches(word, vocab, n=3, cutoff=0.75) or [word]
    _fuzzy_cache[word] = result
    return result

def build_feed(tab, topic, sub, q, seed):
    key = (tab, topic, sub, q, seed)
    if key in cache:
        return cache[key]
    lo, hi = TABS[tab]
    sql = "SELECT v.* FROM videos v WHERE v.duration >= ? AND v.duration < ?"
    params = [lo, hi]
    if topic:
        sql += " AND v.video_id IN (SELECT video_id FROM video_topics WHERE topic = ?"
        params.append(topic)
        if sub:
            sql += " AND subtopic = ?"
            params.append(sub)
        sql += ")"
    for word in q.lower().split():
        options = expand_word(word)
        sql += " AND (" + " OR ".join(
            ["instr(lower(v.title || ' ' || v.channel), ?) > 0"] * len(options)) + ")"
        params.extend(options)

    conn = feed_db()
    rows = [dict(r) for r in conn.execute(sql, params)]
    conn.close()

    if q:  # search: best-scoring matches first
        rows.sort(key=lambda v: v["score"] or 0, reverse=True)
    else:  # browsing: score-weighted shuffle, new order for every seed
        rng = random.Random(seed)
        rows.sort(key=lambda v: rng.random() ** (1 / (math.log1p(max(v["score"] or 0, 0)) + 0.1)),
                  reverse=True)
    if len(cache) > 20:
        cache.clear()
    cache[key] = rows
    return rows

def videos_by_ids(ids):
    if not ids:
        return []
    conn = feed_db()
    marks = ",".join("?" * len(ids))
    found = {r["video_id"]: dict(r) for r in
             conn.execute(f"SELECT * FROM videos WHERE video_id IN ({marks})", ids)}
    conn.close()
    return [found[i] for i in ids if i in found]

def add_flags(rows, uid):
    rows = [dict(r) for r in rows]
    liked, later = set(), set()
    if rows and uid:
        ids = [r["video_id"] for r in rows]
        marks = ",".join("?" * len(ids))
        u = user_db()
        liked = {x[0] for x in u.execute(
            f"SELECT video_id FROM likes WHERE uid=? AND video_id IN ({marks})", [uid, *ids])}
        later = {x[0] for x in u.execute(
            f"SELECT video_id FROM watch_later WHERE uid=? AND video_id IN ({marks})", [uid, *ids])}
        u.close()
    for r in rows:
        r["liked"] = r["video_id"] in liked
        r["later"] = r["video_id"] in later
    return rows

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/videos")
def api_videos():
    view = request.args.get("view", "home")
    page = max(1, request.args.get("page", 1, type=int))
    uid = request.args.get("uid", "")
    start = (page - 1) * PER_PAGE

    if view in LIBRARY:
        u = user_db()
        ids = [r[0] for r in u.execute(
            f"SELECT video_id FROM {LIBRARY[view]} WHERE uid=? ORDER BY ts DESC LIMIT ? OFFSET ?",
            (uid, PER_PAGE, start))]
        u.close()
        rows = videos_by_ids(ids)
    else:
        tab = request.args.get("tab", "videos")
        if tab not in TABS:
            tab = "videos"
        rows = build_feed(
            tab, request.args.get("topic", ""), request.args.get("sub", ""),
            request.args.get("q", "").strip(), request.args.get("seed", 0, type=int),
        )[start:start + PER_PAGE]
    return jsonify(add_flags(rows, uid))

@app.route("/api/topics")
def api_topics():
    conn = feed_db()
    sub_counts = {(t, s): c for t, s, c in conn.execute(
        "SELECT topic, subtopic, COUNT(*) FROM video_topics GROUP BY topic, subtopic")}
    totals = {t: c for t, c in conn.execute(
        "SELECT topic, COUNT(DISTINCT video_id) FROM video_topics GROUP BY topic")}
    conn.close()
    return jsonify([
        {"name": t, "count": totals.get(t, 0),
         "subs": [{"name": s, "count": sub_counts.get((t, s), 0)} for s in subs]}
        for t, subs in TAXONOMY.items()
    ])

@app.route("/api/history", methods=["POST"])
def api_history():
    d = request.get_json()
    u = user_db()
    u.execute("INSERT OR REPLACE INTO history VALUES (?,?,?)", (d["uid"], d["video_id"], time.time()))
    u.commit()
    u.close()
    return jsonify(ok=True)

@app.route("/api/toggle", methods=["POST"])
def api_toggle():
    d = request.get_json()
    table = {"liked": "likes", "later": "watch_later"}.get(d.get("list"))
    if not table:
        return jsonify(ok=False), 400
    u = user_db()
    exists = u.execute(f"SELECT 1 FROM {table} WHERE uid=? AND video_id=?",
                       (d["uid"], d["video_id"])).fetchone()
    if exists:
        u.execute(f"DELETE FROM {table} WHERE uid=? AND video_id=?", (d["uid"], d["video_id"]))
        on = False
    else:
        u.execute(f"INSERT INTO {table} VALUES (?,?,?)", (d["uid"], d["video_id"], time.time()))
        on = True
    u.commit()
    u.close()
    return jsonify(ok=True, on=on)
#  research papers 
PAPERS_PER_PAGE = 20

def papers_db():
    conn = sqlite3.connect("papers.db")
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/papers")
def papers_page():
    return render_template("papers.html")

@app.route("/api/papers")
def api_papers():
    page = max(1, request.args.get("page", 1, type=int))
    sort = request.args.get("sort", "cited")
    kind = request.args.get("kind", "all")
    only_top = request.args.get("top", "0") == "1"
    topic = request.args.get("topic", "")
    q = request.args.get("q", "").strip().lower()

    sql = "SELECT p.* FROM papers p WHERE 1=1"
    params = []
    if kind == "reviewed":
        sql += " AND p.kind IN ('conference', 'journal')"
    elif kind == "preprint":
        sql += " AND p.kind = 'preprint'"
    if only_top:
        sql += " AND p.top = 1"
    if topic:
        sql += " AND p.paper_id IN (SELECT paper_id FROM paper_topics WHERE topic = ?)"
        params.append(topic)
    for word in q.split():
        sql += (" AND instr(lower(COALESCE(p.title,'') || ' ' || COALESCE(p.authors,'') || ' ' || "
                "COALESCE(p.venue_short,'') || ' ' || COALESCE(p.summary,'')), ?) > 0")
        params.append(word)
    order = "COALESCE(p.citations, 0) DESC, p.published DESC" if sort == "cited" else "p.published DESC"
    sql += f" ORDER BY {order} LIMIT ? OFFSET ?"
    params += [PAPERS_PER_PAGE, (page - 1) * PAPERS_PER_PAGE]

    conn = papers_db()
    rows = [dict(r) for r in conn.execute(sql, params)]
    conn.close()
    for r in rows:
        r["summary"] = (r["summary"] or "")[:700]
    return jsonify(rows)

@app.route("/api/paper_topics")
def api_paper_topics():
    conn = papers_db()
    rows = conn.execute(
        "SELECT topic, COUNT(*) AS n FROM paper_topics GROUP BY topic ORDER BY n DESC").fetchall()
    conn.close()
    return jsonify([{"name": r["topic"], "count": r["n"]} for r in rows])
if __name__ == "__main__":
    app.run(debug=True)