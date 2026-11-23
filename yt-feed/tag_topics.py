import sqlite3
from topics import tag_title

conn = sqlite3.connect("feed.db")
conn.execute("""
    CREATE TABLE IF NOT EXISTS video_topics (
        video_id TEXT, topic TEXT, subtopic TEXT,
        PRIMARY KEY (video_id, topic, subtopic)
    )
""")
conn.execute("DELETE FROM video_topics")

rows = conn.execute("SELECT video_id, title FROM videos").fetchall()
tagged = 0
for vid, title in rows:
    tags = tag_title(title)
    for topic, sub in tags:
        conn.execute("INSERT OR IGNORE INTO video_topics VALUES (?,?,?)", (vid, topic, sub))
    if tags:
        tagged += 1
conn.commit()

print(f"Tagged {tagged} of {len(rows)} videos")
for t, c in conn.execute(
    "SELECT topic, COUNT(DISTINCT video_id) FROM video_topics GROUP BY topic ORDER BY 2 DESC"
):
    print(f"  {t}: {c}")