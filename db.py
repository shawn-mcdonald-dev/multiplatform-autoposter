import sqlite3

conn = sqlite3.connect("posts.db", check_same_thread=False)
conn.execute("""
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY,
    filename TEXT,
    status TEXT,
    platform TEXT,
    response TEXT
)
""")
conn.commit()

def log_post(filename, status, platform, response=""):
    conn.execute(
        "INSERT INTO posts (filename, status, platform, response) VALUES (?, ?, ?, ?)",
        (filename, status, platform, response)
    )
    conn.commit()
