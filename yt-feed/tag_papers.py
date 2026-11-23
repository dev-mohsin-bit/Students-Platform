import re
import sqlite3
import topics

# works with either version of topics.py
TAX = getattr(topics, "TAXONOMIES", {}).get("ml") or topics.TAXONOMY
SKIP = {"AI News & Careers", "Research & Papers"}  # video-style topics that don't fit papers

patterns = {
    t: re.compile("|".join(topics._pattern(k) for kws in subs.values() for k in kws), re.I)
    for t, subs in TAX.items() if t not in SKIP
}

conn = sqlite3.connect("papers.db")
conn.execute("CREATE TABLE IF NOT EXISTS paper_topics (paper_id TEXT, topic TEXT, PRIMARY KEY (paper_id, topic))")
conn.execute("DELETE FROM paper_topics")
rows = conn.execute("SELECT paper_id, title FROM papers").fetchall()
tagged = 0
for pid, title in rows:
    hits = [t for t, rx in patterns.items() if rx.search(title or "")]
    for t in hits:
        conn.execute("INSERT OR IGNORE INTO paper_topics VALUES (?,?)", (pid, t))
    if hits:
        tagged += 1
conn.commit()
print(f"Tagged {tagged} of {len(rows)} papers")
for t, c in conn.execute("SELECT topic, COUNT(*) FROM paper_topics GROUP BY topic ORDER BY 2 DESC"):
    print(f"  {t}: {c}")