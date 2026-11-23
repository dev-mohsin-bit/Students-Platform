import os
import sqlite3
import time
import requests
from dotenv import load_dotenv

load_dotenv()
KEY = os.getenv("S2_API_KEY")  # optional, a free key makes this faster and more reliable
URL = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"
FIELDS = ("title,abstract,year,publicationDate,citationCount,influentialCitationCount,"
          "venue,authors,openAccessPdf,externalIds,url")

QUERIES = ['"machine learning"', '"deep learning"', '"neural network"', '"transformer"',
           '"reinforcement learning"', '"computer vision"', '"natural language processing"',
           '"large language model"', '"diffusion model"', '"generative adversarial"']
# (years, minimum citations): newer papers have had less time to be cited, so the bar is lower
RANGES = [("2012-2019", 200), ("2020-2022", 100), ("2023-", 30)]
PAGES_PER_QUERY = 1  # 1 page = up to 1000 papers per query and year range

NEW_COLUMNS = [("source", "TEXT"), ("citations", "INTEGER"), ("influential", "INTEGER"),
               ("venue", "TEXT"), ("oa_pdf", "TEXT")]

def setup_db():
    conn = sqlite3.connect("papers.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS papers (
            paper_id TEXT PRIMARY KEY, title TEXT, authors TEXT, summary TEXT,
            published TEXT, category TEXT, abs_url TEXT, pdf_url TEXT
        )
    """)
    have = [r[1] for r in conn.execute("PRAGMA table_info(papers)")]
    for name, typ in NEW_COLUMNS:
        if name not in have:
            conn.execute(f"ALTER TABLE papers ADD COLUMN {name} {typ}")
    conn.execute("UPDATE papers SET source = 'arxiv' WHERE source IS NULL AND paper_id NOT LIKE 'S2:%'")
    conn.commit()
    return conn

def get_page(params):
    headers = {"x-api-key": KEY} if KEY else {}
    for attempt in range(6):
        r = requests.get(URL, params=params, headers=headers, timeout=60)
        if r.status_code == 200:
            return r.json()
        if r.status_code in (429, 500, 502, 503, 504):
            wait = 5 * (attempt + 1)
            print(f"  server said {r.status_code}, waiting {wait}s...")
            time.sleep(wait)
            continue
        print("  error", r.status_code, r.text[:200])
        return None
    return None

def save(conn, items):
    n = 0
    for it in items:
        title = " ".join((it.get("title") or "").split())
        if not title:
            continue
        ext = it.get("externalIds") or {}
        paper_id = ext.get("ArXiv") or "S2:" + it["paperId"]  # same paper from arXiv is merged, not duplicated
        authors = ", ".join(a["name"] for a in (it.get("authors") or [])[:10] if a.get("name"))
        published = it.get("publicationDate") or (f"{it['year']}-01-01" if it.get("year") else "")
        pdf = (it.get("openAccessPdf") or {}).get("url") or ""
        conn.execute("""
            INSERT INTO papers (paper_id, title, authors, summary, published, category, abs_url, pdf_url,
                                source, citations, influential, venue, oa_pdf)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(paper_id) DO UPDATE SET
                citations = excluded.citations, influential = excluded.influential,
                venue = excluded.venue, oa_pdf = excluded.oa_pdf
        """, (paper_id, title, authors, " ".join((it.get("abstract") or "").split()), published,
              "Computer Science", it.get("url") or "", pdf, "semanticscholar",
              it.get("citationCount") or 0, it.get("influentialCitationCount") or 0,
              it.get("venue") or "", pdf))
        n += 1
    conn.commit()
    return n

if __name__ == "__main__":
    conn = setup_db()
    for query in QUERIES:
        for years, min_cites in RANGES:
            params = {"query": query, "year": years, "fieldsOfStudy": "Computer Science",
                      "minCitationCount": min_cites, "sort": "citationCount:desc", "fields": FIELDS}
            total = 0
            for page in range(PAGES_PER_QUERY):
                data = get_page(params)
                if not data:
                    break
                total += save(conn, data.get("data", []))
                if not data.get("token"):
                    break
                params["token"] = data["token"]
                time.sleep(1.5)
            print(f"{query} {years}: processed {total}")
            time.sleep(1.5)

    print("\nTotal papers in database:", conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0])
    for source, n in conn.execute("SELECT source, COUNT(*) FROM papers GROUP BY source"):
        print(f"  {source}: {n}")
    print("\nMost cited:")
    for title, c, venue, pub in conn.execute(
            "SELECT title, citations, venue, published FROM papers ORDER BY citations DESC LIMIT 5"):
        print(f"- {title} ({pub[:4]}, {venue or 'no venue'}): {c:,} citations")