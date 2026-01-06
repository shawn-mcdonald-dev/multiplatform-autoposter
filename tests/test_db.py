"""Unit tests for database logging."""

import sqlite3
import pytest
from unittest.mock import patch, MagicMock

import db
from db import log_post


class TestLogPost:
    """Tests for the log_post function."""

    def test_log_post_inserts_record(self, in_memory_db):
        """Should insert a record into the database."""
        with patch.object(db, "conn", in_memory_db):
            log_post("test_video.mp4", "POSTED", "tiktok", '{"success": true}')

            cursor = in_memory_db.execute("SELECT * FROM posts")
            rows = cursor.fetchall()

            assert len(rows) == 1
            assert rows[0][1] == "test_video.mp4"  # filename
            assert rows[0][2] == "POSTED"  # status
            assert rows[0][3] == "tiktok"  # platform
            assert rows[0][4] == '{"success": true}'  # response

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

    def test_log_post_different_platforms(self, in_memory_db):
        """Should correctly log different platforms."""
        with patch.object(db, "conn", in_memory_db):
            log_post("video.mp4", "POSTED", "tiktok", "")
            log_post("video.mp4", "POSTED", "youtube", "")
            log_post("video.mp4", "POSTED", "instagram", "")

            cursor = in_memory_db.execute("SELECT DISTINCT platform FROM posts")
            platforms = [row[0] for row in cursor.fetchall()]

            assert set(platforms) == {"tiktok", "youtube", "instagram"}

    def test_log_post_different_statuses(self, in_memory_db):
        """Should correctly log different statuses."""
        with patch.object(db, "conn", in_memory_db):
            log_post("video1.mp4", "POSTED", "tiktok", "")
            log_post("video2.mp4", "FAILED", "tiktok", "")
            log_post("video3.mp4", "PENDING", "tiktok", "")

            cursor = in_memory_db.execute("SELECT status FROM posts ORDER BY id")
            statuses = [row[0] for row in cursor.fetchall()]

            assert statuses == ["POSTED", "FAILED", "PENDING"]

    def test_log_post_special_characters_in_filename(self, in_memory_db):
        """Should handle special characters in filename."""
        with patch.object(db, "conn", in_memory_db):
            filename = "my video (1) - final [2024].mp4"
            log_post(filename, "POSTED", "tiktok", "")

            cursor = in_memory_db.execute("SELECT filename FROM posts")
            row = cursor.fetchone()

            assert row[0] == filename

    def test_log_post_long_response(self, in_memory_db):
        """Should handle long response strings."""
        with patch.object(db, "conn", in_memory_db):
            long_response = "x" * 10000
            log_post("video.mp4", "POSTED", "tiktok", long_response)

            cursor = in_memory_db.execute("SELECT response FROM posts")
            row = cursor.fetchone()

            assert row[0] == long_response
            assert len(row[0]) == 10000


class TestDatabaseSchema:
    """Tests for database schema."""

    def test_posts_table_has_correct_columns(self, in_memory_db):
        """Should have all required columns."""
        cursor = in_memory_db.execute("PRAGMA table_info(posts)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        assert "id" in columns
        assert "filename" in columns
        assert "status" in columns
        assert "platform" in columns
        assert "response" in columns

    def test_id_is_primary_key(self, in_memory_db):
        """Should have id as primary key."""
        cursor = in_memory_db.execute("PRAGMA table_info(posts)")
        for row in cursor.fetchall():
            if row[1] == "id":
                assert row[5] == 1  # pk column

    def test_id_auto_increments(self, in_memory_db):
        """Should auto-increment id."""
        with patch.object(db, "conn", in_memory_db):
            log_post("video1.mp4", "POSTED", "tiktok", "")
            log_post("video2.mp4", "POSTED", "tiktok", "")

            cursor = in_memory_db.execute("SELECT id FROM posts ORDER BY id")
            ids = [row[0] for row in cursor.fetchall()]

            assert ids == [1, 2]


class TestDatabaseConnection:
    """Tests for database connection handling."""

    def test_module_creates_table_on_import(self):
        """Should create posts table when module is imported."""
        # The actual db module creates the table on import
        cursor = db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='posts'"
        )
        result = cursor.fetchone()
        assert result is not None
        assert result[0] == "posts"

