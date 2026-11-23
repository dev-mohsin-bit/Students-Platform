import re
import sqlite3

conn = sqlite3.connect("papers.db")
have = [r[1] for r in conn.execute("PRAGMA table_info(papers)")]
for name, typ in [("kind", "TEXT"), ("top", "INTEGER"), ("venue_short", "TEXT")]:
    if name not in have:
        conn.execute(f"ALTER TABLE papers ADD COLUMN {name} {typ}")

# Starting list of top venues. This is my judgement, not an official ranking, so edit it freely.
TOP_CONFERENCES = {
    "NeurIPS": r"neural information processing|\bneurips\b|\bnips\b",
    "ICML": r"international conference on machine learning|\bicml\b",
    "ICLR": r"international conference on learning representations|\biclr\b",
    "CVPR": r"computer vision and pattern recognition|\bcvpr\b",
    "ICCV": r"international conference on computer vision|\biccv\b",
    "ECCV": r"european conference on computer vision|\beccv\b",
    "AAAI": r"aaai conference on artificial intelligence",
    "ACL": r"annual meeting of the association for computational linguistics",
    "EMNLP": r"empirical methods in natural language processing",
    "NAACL": r"north american chapter of the association for computational linguistics",
}
TOP_JOURNALS = {
    "TPAMI": r"pattern analysis and machine intelligence",
    "TNNLS": r"neural networks and learning systems",
    "JMLR": r"journal of machine learning research",
    "IJCV": r"international journal of computer vision",
    "ACM Computing Surveys": r"acm computing surveys",
    "Nature": r"^nature$",
    "Science": r"^science$",
    "Nature Machine Intelligence": r"nature machine intelligence",
}
TOP_CONF = {k: re.compile(v, re.I) for k, v in TOP_CONFERENCES.items()}
TOP_JOUR = {k: re.compile(v, re.I) for k, v in TOP_JOURNALS.items()}
PREPRINT = re.compile(r"arxiv|biorxiv|medrxiv|ssrn|research square|preprint", re.I)
CONF = re.compile(r"conference|proceedings|workshop|symposium|annual meeting", re.I)

def label(venue):
    v = (venue or "").strip()
    for short, rx in TOP_CONF.items():
        if rx.search(v):
            return "conference", 1, short
    for short, rx in TOP_JOUR.items():
        if rx.search(v):
            return "journal", 1, short
    if not v or PREPRINT.search(v):
        return "preprint", 0, v
    if CONF.search(v):
        return "conference", 0, v
    return "journal", 0, v

rows = conn.execute("SELECT paper_id, venue FROM papers").fetchall()
for pid, venue in rows:
    kind, top, short = label(venue)
    conn.execute("UPDATE papers SET kind=?, top=?, venue_short=? WHERE paper_id=?", (kind, top, short, pid))
conn.commit()

print("Papers by kind (top-venue papers in brackets):")
for kind, n, tops in conn.execute("SELECT kind, COUNT(*), SUM(top) FROM papers GROUP BY kind ORDER BY 2 DESC"):
    print(f"  {kind}: {n} [{tops or 0} top]")
print("\nTop venues:")
for short, n in conn.execute(
        "SELECT venue_short, COUNT(*) FROM papers WHERE top = 1 GROUP BY venue_short ORDER BY 2 DESC"):
    print(f"  {n:5}  {short}")