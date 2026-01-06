"""Unit tests for TikTok API integration."""

import os
import pytest
from unittest.mock import patch, MagicMock, mock_open

from tiktok import (
    post_video,
    get_access_token,
    _init_video_upload,
    _upload_video_chunks,
    _check_publish_status,
    TikTokAPIError,
    MissingTokenError,
    CHUNK_SIZE,
)


class TestGetAccessToken:
    """Tests for get_access_token function."""

    def test_returns_token_when_set(self, env_with_token, mock_access_token):
        """Should return the token when environment variable is set."""
        token = get_access_token()
        assert token == mock_access_token

    def test_raises_error_when_not_set(self, env_without_token):
        """Should raise MissingTokenError when token is not set."""
        with pytest.raises(MissingTokenError) as exc_info:
            get_access_token()
        assert "TIKTOK_ACCESS_TOKEN" in str(exc_info.value)


class TestInitVideoUpload:
    """Tests for _init_video_upload function."""

    def test_successful_init(self, mock_access_token, mock_tiktok_init_response):
        """Should return publish_id and upload_url on success."""
        with patch("tiktok.requests.post") as mock_post:
            mock_post.return_value.json.return_value = mock_tiktok_init_response

            result = _init_video_upload(mock_access_token, 1000000)

            assert result["publish_id"] == "test_publish_id_12345"
            assert "upload_url" in result
            mock_post.assert_called_once()

    def test_api_error_response(self, mock_access_token, mock_tiktok_error_response):
        """Should raise TikTokAPIError on error response."""
        with patch("tiktok.requests.post") as mock_post:
            mock_post.return_value.json.return_value = mock_tiktok_error_response

            with pytest.raises(TikTokAPIError) as exc_info:
                _init_video_upload(mock_access_token, 1000000)

            assert exc_info.value.code == "invalid_token"

    def test_correct_headers_sent(self, mock_access_token, mock_tiktok_init_response):
        """Should send correct authorization headers."""
        with patch("tiktok.requests.post") as mock_post:
            mock_post.return_value.json.return_value = mock_tiktok_init_response

            _init_video_upload(mock_access_token, 1000000)

            call_kwargs = mock_post.call_args.kwargs
            assert f"Bearer {mock_access_token}" in call_kwargs["headers"]["Authorization"]


class TestUploadVideoChunks:
    """Tests for _upload_video_chunks function."""

    def test_successful_single_chunk_upload(self, mock_video_file):
        """Should successfully upload a small file in one chunk."""
        with patch("tiktok.requests.put") as mock_put:
            mock_put.return_value.status_code = 200

            _upload_video_chunks(
                "https://upload.example.com",
                mock_video_file,
                os.path.getsize(mock_video_file),
            )

            mock_put.assert_called_once()

    def test_upload_failure_raises_error(self, mock_video_file):
        """Should raise TikTokAPIError on upload failure."""
        with patch("tiktok.requests.put") as mock_put:
            mock_put.return_value.status_code = 500

            with pytest.raises(TikTokAPIError) as exc_info:
                _upload_video_chunks(
                    "https://upload.example.com",
                    mock_video_file,
                    os.path.getsize(mock_video_file),
                )

            assert exc_info.value.code == "upload_failed"

    def test_content_range_header_set(self, mock_video_file):
        """Should set Content-Range header correctly."""
        with patch("tiktok.requests.put") as mock_put:
            mock_put.return_value.status_code = 200
            file_size = os.path.getsize(mock_video_file)

            _upload_video_chunks(
                "https://upload.example.com",
                mock_video_file,
                file_size,
            )

            call_kwargs = mock_put.call_args.kwargs
            assert "Content-Range" in call_kwargs["headers"]


class TestCheckPublishStatus:
    """Tests for _check_publish_status function."""

    def test_successful_status_check(
        self, mock_access_token, mock_tiktok_status_response_success
    ):
        """Should return status data on success."""
        with patch("tiktok.requests.post") as mock_post:
            mock_post.return_value.json.return_value = mock_tiktok_status_response_success

            result = _check_publish_status(mock_access_token, "test_publish_id")

            assert result["status"] == "PUBLISH_COMPLETE"

    def test_processing_status(
        self, mock_access_token, mock_tiktok_status_response_processing
    ):
        """Should return processing status when still uploading."""
        with patch("tiktok.requests.post") as mock_post:
            mock_post.return_value.json.return_value = mock_tiktok_status_response_processing

            result = _check_publish_status(mock_access_token, "test_publish_id")

            assert result["status"] == "PROCESSING_UPLOAD"

    def test_error_response(self, mock_access_token, mock_tiktok_error_response):
        """Should raise TikTokAPIError on error response."""
        with patch("tiktok.requests.post") as mock_post:
            mock_post.return_value.json.return_value = mock_tiktok_error_response

            with pytest.raises(TikTokAPIError):
                _check_publish_status(mock_access_token, "test_publish_id")


class TestPostVideo:
    """Tests for the main post_video function."""

    def test_successful_post(
        self,
        env_with_token,
        mock_video_file,
        mock_tiktok_init_response,
        mock_tiktok_status_response_success,
    ):
        """Should successfully post a video and return result."""
        with patch("tiktok.requests.post") as mock_post, patch(
            "tiktok.requests.put"
        ) as mock_put:
            # First call is init, second call is status check
            mock_post.return_value.json.side_effect = [
                mock_tiktok_init_response,
                mock_tiktok_status_response_success,
            ]
            mock_put.return_value.status_code = 200

            result = post_video(mock_video_file)

            assert result["success"] is True
            assert result["publish_id"] == "test_publish_id_12345"
            assert result["status"] == "PUBLISH_COMPLETE"

    def test_missing_token_raises_error(self, env_without_token, mock_video_file):
        """Should raise MissingTokenError when token not set."""
        with pytest.raises(MissingTokenError):
            post_video(mock_video_file)

    def test_file_not_found_raises_error(self, env_with_token):
        """Should raise FileNotFoundError for non-existent file."""
        with pytest.raises(FileNotFoundError):
            post_video("/nonexistent/path/video.mp4")

    def test_api_error_propagates(
        self, env_with_token, mock_video_file, mock_tiktok_error_response
    ):
        """Should propagate TikTokAPIError from init."""
        with patch("tiktok.requests.post") as mock_post:
            mock_post.return_value.json.return_value = mock_tiktok_error_response

            with pytest.raises(TikTokAPIError):
                post_video(mock_video_file)


class TestTikTokAPIError:
    """Tests for TikTokAPIError exception."""

    def test_error_message_format(self):
        """Should format error message correctly."""
        error = TikTokAPIError("test_code", "Test message")
        assert error.code == "test_code"
        assert error.message == "Test message"
        assert "test_code" in str(error)
        assert "Test message" in str(error)


class TestMissingTokenError:
    """Tests for MissingTokenError exception."""

    def test_error_message(self):
        """Should include helpful message about setting token."""
        error = MissingTokenError()
        assert "TIKTOK_ACCESS_TOKEN" in str(error)

