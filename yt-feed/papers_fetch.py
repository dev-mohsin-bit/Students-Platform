import re
import sqlite3
import time
import feedparser

CATEGORIES = ["cs.LG", "cs.CL", "cs.CV", "cs.AI", "stat.ML"]
PAGE_SIZE = 100
PAGES = 5  # newest 500 papers per category

def setup_db():
    conn = sqlite3.connect("papers.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS papers (
            paper_id TEXT PRIMARY KEY, title TEXT, authors TEXT, summary TEXT,
            published TEXT, category TEXT, abs_url TEXT, pdf_url TEXT
        )
    """)
    return conn

def fetch_category(cat):
    papers = []
    for i in range(PAGES):
        url = ("https://export.arxiv.org/api/query?search_query=cat:" + cat +
               f"&sortBy=submittedDate&sortOrder=descending&start={i * PAGE_SIZE}&max_results={PAGE_SIZE}")
        feed = feedparser.parse(url)
        if not feed.entries:
            break
        for e in feed.entries:
            abs_url = e.link
            paper_id = re.sub(r"v\d+$", "", abs_url.split("/abs/")[-1])
            pdf_url = next((l.href for l in e.links if l.get("type") == "application/pdf"),
                           abs_url.replace("/abs/", "/pdf/"))
            authors = ", ".join(a.name for a in e.get("authors", []))
            primary = e.get("arxiv_primary_category", {}).get("term", cat)
            papers.append((
                paper_id, " ".join(e.title.split()), authors, " ".join(e.summary.split()),
                e.published, primary, abs_url, pdf_url,
            ))
        time.sleep(3)  # arXiv asks for about one request every 3 seconds
    return papers

if __name__ == "__main__":
    conn = setup_db()
    for cat in CATEGORIES:
        papers = fetch_category(cat)
        conn.executemany(
            "INSERT OR IGNORE INTO papers (paper_id, title, authors, summary, published, category, abs_url, pdf_url, source) "
            "VALUES (?,?,?,?,?,?,?,?,'arxiv')", papers)
        conn.commit()
        print(f"{cat}: fetched {len(papers)} papers")
    total = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
    print("Total papers in database:", total)
    print("\nNewest 5:")
    for title, authors, published in conn.execute(
            "SELECT title, authors, published FROM papers ORDER BY published DESC LIMIT 5"):
        print(f"- {title} ({published[:10]})\n  {authors[:80]}")