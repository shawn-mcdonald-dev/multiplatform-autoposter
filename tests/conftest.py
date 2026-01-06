"""Shared test fixtures for autoposter-core tests."""

import os
import tempfile
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def mock_video_file():
    """Create a temporary mock video file for testing."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        # Write some dummy bytes to simulate a video file
        f.write(b"fake video content " * 1000)
        f.flush()
        yield f.name
    # Cleanup
    if os.path.exists(f.name):
        os.unlink(f.name)


@pytest.fixture
def mock_video_bytes():
    """Return mock video bytes for upload testing."""
    return b"fake video content " * 1000


@pytest.fixture
def mock_tiktok_init_response():
    """Mock successful TikTok init response."""
    return {
        "data": {
            "publish_id": "test_publish_id_12345",
            "upload_url": "https://open-upload.tiktokapis.com/video/?upload_id=test123"
        },
        "error": {
            "code": "ok",
            "message": ""
        }
    }


@pytest.fixture
def mock_tiktok_status_response_success():
    """Mock successful TikTok status response."""
    return {
        "data": {
            "status": "PUBLISH_COMPLETE",
            "publish_id": "test_publish_id_12345"
        },
        "error": {
            "code": "ok",
            "message": ""
        }
    }


@pytest.fixture
def mock_tiktok_status_response_processing():
    """Mock TikTok status response when still processing."""
    return {
        "data": {
            "status": "PROCESSING_UPLOAD",
            "publish_id": "test_publish_id_12345"
        },
        "error": {
            "code": "ok",
            "message": ""
        }
    }


@pytest.fixture
def mock_tiktok_error_response():
    """Mock TikTok error response."""
    return {
        "data": {},
        "error": {
            "code": "invalid_token",
            "message": "The access token is invalid or has expired."
        }
    }


@pytest.fixture
def mock_access_token():
    """Provide a mock access token."""
    return "test_access_token_abc123"


@pytest.fixture
def env_with_token(mock_access_token):
    """Set up environment with mock access token."""
    with patch.dict(os.environ, {"TIKTOK_ACCESS_TOKEN": mock_access_token}):
        yield mock_access_token


@pytest.fixture
def env_without_token():
    """Set up environment without access token."""
    env = os.environ.copy()
    env.pop("TIKTOK_ACCESS_TOKEN", None)
    with patch.dict(os.environ, env, clear=True):
        yield


@pytest.fixture
def test_client():
    """Create a FastAPI test client."""
    from main import app
    return TestClient(app)


@pytest.fixture
def in_memory_db():
    """Create an in-memory SQLite database for testing."""
    import sqlite3
    conn = sqlite3.connect(":memory:", check_same_thread=False)
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
    yield conn
    conn.close()


@pytest.fixture
def temp_uploads_dir():
    """Create a temporary uploads directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        uploads_path = os.path.join(tmpdir, "uploads")
        os.makedirs(uploads_path)
        yield uploads_path

