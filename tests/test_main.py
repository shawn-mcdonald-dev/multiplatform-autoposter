"""Unit tests for FastAPI endpoints."""

import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from io import BytesIO

from main import app, UPLOADS_DIR
from tiktok import MissingTokenError, TikTokAPIError


@pytest.fixture
def client():
    """Create test client with uploads directory."""
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    return TestClient(app)


@pytest.fixture
def cleanup_uploads():
    """Clean up uploaded files after tests."""
    yield
    # Cleanup any test files
    if os.path.exists(UPLOADS_DIR):
        for f in os.listdir(UPLOADS_DIR):
            if f.startswith("test_"):
                os.remove(os.path.join(UPLOADS_DIR, f))


class TestUploadEndpoint:
    """Tests for the /upload endpoint."""

    def test_successful_upload(self, client, mock_video_bytes, cleanup_uploads):
        """Should return success when video posts successfully."""
        mock_result = {
            "success": True,
            "publish_id": "test_123",
            "status": "PUBLISH_COMPLETE",
        }

        with patch("main.post_video", return_value=mock_result) as mock_post, patch(
            "main.log_post"
        ) as mock_log:
            response = client.post(
                "/upload",
                files={"file": ("test_video.mp4", BytesIO(mock_video_bytes), "video/mp4")},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "posted"
            assert data["platform"] == "tiktok"
            assert data["result"] == mock_result

            # Verify logging was called with success
            mock_log.assert_called_once()
            call_args = mock_log.call_args[0]
            assert call_args[1] == "POSTED"

    def test_missing_token_error(self, client, mock_video_bytes, cleanup_uploads):
        """Should return 500 when TikTok token is not configured."""
        with patch("main.post_video", side_effect=MissingTokenError()) as mock_post, patch(
            "main.log_post"
        ) as mock_log:
            response = client.post(
                "/upload",
                files={"file": ("test_video.mp4", BytesIO(mock_video_bytes), "video/mp4")},
            )

            assert response.status_code == 500
            assert "TIKTOK_ACCESS_TOKEN" in response.json()["detail"]

            # Verify logging was called with failure
            mock_log.assert_called_once()
            call_args = mock_log.call_args[0]
            assert call_args[1] == "FAILED"

    def test_tiktok_api_error(self, client, mock_video_bytes, cleanup_uploads):
        """Should return 502 when TikTok API returns an error."""
        with patch(
            "main.post_video",
            side_effect=TikTokAPIError("rate_limit", "Too many requests"),
        ) as mock_post, patch("main.log_post") as mock_log:
            response = client.post(
                "/upload",
                files={"file": ("test_video.mp4", BytesIO(mock_video_bytes), "video/mp4")},
            )

            assert response.status_code == 502
            assert "Too many requests" in response.json()["detail"]

    def test_generic_error(self, client, mock_video_bytes, cleanup_uploads):
        """Should return 500 for unexpected errors."""
        with patch(
            "main.post_video", side_effect=Exception("Unexpected error")
        ) as mock_post, patch("main.log_post") as mock_log:
            response = client.post(
                "/upload",
                files={"file": ("test_video.mp4", BytesIO(mock_video_bytes), "video/mp4")},
            )

            assert response.status_code == 500
            assert "Unexpected error" in response.json()["detail"]

    def test_file_saved_to_uploads(self, client, mock_video_bytes, cleanup_uploads):
        """Should save uploaded file to uploads directory."""
        mock_result = {"success": True, "publish_id": "test_123", "status": "COMPLETE"}

        with patch("main.post_video", return_value=mock_result), patch("main.log_post"):
            response = client.post(
                "/upload",
                files={
                    "file": ("test_saved_video.mp4", BytesIO(mock_video_bytes), "video/mp4")
                },
            )

            assert response.status_code == 200
            # Verify file was saved
            saved_path = os.path.join(UPLOADS_DIR, "test_saved_video.mp4")
            assert os.path.exists(saved_path)

    def test_post_video_called_with_correct_path(
        self, client, mock_video_bytes, cleanup_uploads
    ):
        """Should call post_video with the correct file path."""
        mock_result = {"success": True, "publish_id": "test_123", "status": "COMPLETE"}

        with patch("main.post_video", return_value=mock_result) as mock_post, patch(
            "main.log_post"
        ):
            response = client.post(
                "/upload",
                files={
                    "file": ("test_path_video.mp4", BytesIO(mock_video_bytes), "video/mp4")
                },
            )

            expected_path = os.path.join(UPLOADS_DIR, "test_path_video.mp4")
            mock_post.assert_called_once_with(expected_path)


class TestAppConfiguration:
    """Tests for application configuration."""

    def test_app_metadata(self):
        """Should have correct app metadata."""
        assert app.title == "Autoposter Core"
        assert app.version == "0.1.0"

    def test_uploads_dir_created_on_startup(self, client):
        """Should create uploads directory on startup."""
        # The client fixture triggers app startup
        assert os.path.exists(UPLOADS_DIR)

