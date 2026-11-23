import sqlite3

conn = sqlite3.connect("papers.db")
total = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
no_venue = conn.execute("SELECT COUNT(*) FROM papers WHERE venue IS NULL OR venue = ''").fetchone()[0]
print(f"{total} papers, {no_venue} with no venue (mostly preprints)\n")
print("Top venues:")
for venue, n in conn.execute(
        "SELECT venue, COUNT(*) FROM papers WHERE venue != '' GROUP BY venue ORDER BY 2 DESC LIMIT 25"):
    print(f"  {n:5}  {venue}")