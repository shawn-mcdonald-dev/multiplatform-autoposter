"""Unit tests for database logging."""

import pytest
from unittest.mock import patch

import db
from db import log_post, create_user, get_user_by_username, save_tiktok_tokens, get_tiktok_tokens


class TestLogPost:
    """Tests for the log_post function."""

    def test_log_post_inserts_record(self, in_memory_db):
        """Should insert a record into the database."""
        with patch.object(db, "conn", in_memory_db):
            log_post("test_video.mp4", "POSTED", "tiktok", '{"success": true}')

            cursor = in_memory_db.execute("SELECT filename, status, platform, response FROM posts")
            row = cursor.fetchone()

            assert row[0] == "test_video.mp4"
            assert row[1] == "POSTED"
            assert row[2] == "tiktok"
            assert row[3] == '{"success": true}'

    def test_log_post_with_user_id(self, in_memory_db):
        """Should insert a record with user_id."""
        with patch.object(db, "conn", in_memory_db):
            user_id = create_user("testuser", "hash")
            log_post("test_video.mp4", "POSTED", "tiktok", "", user_id)

            cursor = in_memory_db.execute("SELECT user_id FROM posts")
            row = cursor.fetchone()
            assert row[0] == user_id

    def test_log_post_with_empty_response(self, in_memory_db):
        """Should handle empty response string."""
        with patch.object(db, "conn", in_memory_db):
            log_post("test_video.mp4", "FAILED", "tiktok", "")

            cursor = in_memory_db.execute("SELECT response FROM posts")
            row = cursor.fetchone()
            assert row[0] == ""

    def test_log_post_multiple_entries(self, in_memory_db):
        """Should handle multiple log entries."""
        with patch.object(db, "conn", in_memory_db):
            log_post("video1.mp4", "POSTED", "tiktok", "result1")
            log_post("video2.mp4", "FAILED", "tiktok", "error")
            log_post("video3.mp4", "POSTED", "youtube", "result3")

            cursor = in_memory_db.execute("SELECT COUNT(*) FROM posts")
            count = cursor.fetchone()[0]
            assert count == 3


class TestUserFunctions:
    """Tests for user database functions."""

    def test_create_user(self, in_memory_db):
        """Should create a user and return ID."""
        with patch.object(db, "conn", in_memory_db):
            user_id = create_user("testuser", "hashed_password")
            assert user_id > 0

    def test_get_user_by_username(self, in_memory_db):
        """Should retrieve user by username."""
        with patch.object(db, "conn", in_memory_db):
            create_user("testuser", "hashed_password")
            user = get_user_by_username("testuser")

            assert user is not None
            assert user["username"] == "testuser"
            assert user["password_hash"] == "hashed_password"

    def test_get_nonexistent_user(self, in_memory_db):
        """Should return None for nonexistent user."""
        with patch.object(db, "conn", in_memory_db):
            user = get_user_by_username("nonexistent")
            assert user is None


class TestTikTokTokens:
    """Tests for TikTok token storage."""

    def test_save_and_get_tokens(self, in_memory_db):
        """Should save and retrieve TikTok tokens."""
        with patch.object(db, "conn", in_memory_db):
            user_id = create_user("testuser", "hash")
            save_tiktok_tokens(user_id, "access_123", "refresh_456", 3600)

            tokens = get_tiktok_tokens(user_id)
            assert tokens["access_token"] == "access_123"
            assert tokens["refresh_token"] == "refresh_456"
            assert tokens["expires_at"] == 3600

    def test_get_tokens_no_tokens(self, in_memory_db):
        """Should return None when user has no tokens."""
        with patch.object(db, "conn", in_memory_db):
            user_id = create_user("testuser", "hash")
            tokens = get_tiktok_tokens(user_id)
            assert tokens is None

    def test_save_tokens_replaces_old(self, in_memory_db):
        """Should replace old tokens when saving new ones."""
        with patch.object(db, "conn", in_memory_db):
            user_id = create_user("testuser", "hash")
            save_tiktok_tokens(user_id, "old_token", "old_refresh", 1000)
            save_tiktok_tokens(user_id, "new_token", "new_refresh", 2000)

            tokens = get_tiktok_tokens(user_id)
            assert tokens["access_token"] == "new_token"


class TestDatabaseConnection:
    """Tests for database connection handling."""

    def test_module_creates_tables_on_import(self):
        """Should create tables when module is imported."""
        cursor = db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='posts'"
        )
        assert cursor.fetchone() is not None

        cursor = db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
        )
        assert cursor.fetchone() is not None
