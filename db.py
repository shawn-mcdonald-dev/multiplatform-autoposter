"""Database management for autoposter-core."""

import sqlite3
from typing import Optional

conn = sqlite3.connect("posts.db", check_same_thread=False)

# Enable foreign keys
conn.execute("PRAGMA foreign_keys = ON")

# Create tables
conn.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

conn.execute("""
CREATE TABLE IF NOT EXISTS tiktok_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    expires_at INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)
""")

conn.execute("""
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    filename TEXT,
    status TEXT,
    platform TEXT,
    response TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
)
""")

conn.commit()


def log_post(filename: str, status: str, platform: str, response: str = "", user_id: Optional[int] = None):
    """Log a post attempt to the database."""
    conn.execute(
        "INSERT INTO posts (user_id, filename, status, platform, response) VALUES (?, ?, ?, ?, ?)",
        (user_id, filename, status, platform, response)
    )
    conn.commit()


def create_user(username: str, password_hash: str) -> int:
    """Create a new user and return their ID."""
    cursor = conn.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        (username, password_hash)
    )
    conn.commit()
    return cursor.lastrowid


def get_user_by_username(username: str) -> Optional[dict]:
    """Get a user by username."""
    cursor = conn.execute(
        "SELECT id, username, password_hash, created_at FROM users WHERE username = ?",
        (username,)
    )
    row = cursor.fetchone()
    if row:
        return {
            "id": row[0],
            "username": row[1],
            "password_hash": row[2],
            "created_at": row[3]
        }
    return None


def get_user_by_id(user_id: int) -> Optional[dict]:
    """Get a user by ID."""
    cursor = conn.execute(
        "SELECT id, username, password_hash, created_at FROM users WHERE id = ?",
        (user_id,)
    )
    row = cursor.fetchone()
    if row:
        return {
            "id": row[0],
            "username": row[1],
            "password_hash": row[2],
            "created_at": row[3]
        }
    return None


def save_tiktok_tokens(user_id: int, access_token: str, refresh_token: Optional[str] = None, 
                       expires_at: Optional[int] = None):
    """Save or update TikTok tokens for a user."""
    conn.execute("DELETE FROM tiktok_tokens WHERE user_id = ?", (user_id,))
    conn.execute(
        "INSERT INTO tiktok_tokens (user_id, access_token, refresh_token, expires_at) VALUES (?, ?, ?, ?)",
        (user_id, access_token, refresh_token, expires_at)
    )
    conn.commit()


def get_tiktok_tokens(user_id: int) -> Optional[dict]:
    """Get TikTok tokens for a user."""
    cursor = conn.execute(
        "SELECT access_token, refresh_token, expires_at FROM tiktok_tokens WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
        (user_id,)
    )
    row = cursor.fetchone()
    if row:
        return {
            "access_token": row[0],
            "refresh_token": row[1],
            "expires_at": row[2]
        }
    return None


def has_tiktok_linked(user_id: int) -> bool:
    """Check if a user has linked their TikTok account."""
    cursor = conn.execute(
        "SELECT COUNT(*) FROM tiktok_tokens WHERE user_id = ?",
        (user_id,)
    )
    return cursor.fetchone()[0] > 0
