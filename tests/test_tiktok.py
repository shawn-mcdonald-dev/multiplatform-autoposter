"""Unit tests for TikTok API integration."""

import os
import pytest
from unittest.mock import patch

import tiktok
from tiktok import (
    post_video,
    get_access_token,
    get_authorization_url,
    exchange_code_for_token,
    _init_video_upload,
    _upload_video_chunks,
    _check_publish_status,
    TikTokAPIError,
    MissingTokenError,
    MissingOAuthConfigError,
)


class TestGetAccessToken:
    """Tests for get_access_token function."""

    def test_returns_token_when_set(self, env_with_token, mock_access_token):
        """Should return the token when environment variable is set."""
        token = get_access_token()
        assert token == mock_access_token

    def test_raises_error_when_not_set(self):
        """Should raise MissingTokenError when token is not set."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(MissingTokenError):
                get_access_token()


class TestOAuthFunctions:
    """Tests for OAuth functions."""

    def test_get_authorization_url_success(self):
        """Should generate authorization URL with state."""
        with patch.dict(os.environ, {
            "TIKTOK_CLIENT_KEY": "test_key",
            "TIKTOK_REDIRECT_URI": "http://localhost:8000/callback",
        }):
            import importlib
            importlib.reload(tiktok)

            auth_url, state = tiktok.get_authorization_url()
            assert "tiktok.com" in auth_url
            assert "test_key" in auth_url
            assert len(state) > 20

    def test_exchange_code_for_token_success(self):
        """Should exchange code for token."""
        mock_response = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "expires_in": 3600,
            "token_type": "Bearer",
        }

        with patch.dict(os.environ, {
            "TIKTOK_CLIENT_KEY": "test_key",
            "TIKTOK_CLIENT_SECRET": "test_secret",
            "TIKTOK_REDIRECT_URI": "http://localhost:8000/callback",
        }), patch("tiktok.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = mock_response

            import importlib
            importlib.reload(tiktok)

            result = tiktok.exchange_code_for_token("test_code")
            assert result["access_token"] == "test_access_token"


class TestInitVideoUpload:
    """Tests for _init_video_upload function."""

    def test_successful_init(self, mock_access_token, mock_tiktok_init_response):
        """Should return publish_id and upload_url on success."""
        with patch("tiktok.requests.post") as mock_post:
            mock_post.return_value.json.return_value = mock_tiktok_init_response

            result = _init_video_upload(mock_access_token, 1000000)

            assert result["publish_id"] == "test_publish_id_12345"
            assert "upload_url" in result

    def test_api_error_response(self, mock_access_token, mock_tiktok_error_response):
        """Should raise TikTokAPIError on error response."""
        with patch("tiktok.requests.post") as mock_post:
            mock_post.return_value.json.return_value = mock_tiktok_error_response

            with pytest.raises(tiktok.TikTokAPIError):
                _init_video_upload(mock_access_token, 1000000)


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

            with pytest.raises(tiktok.TikTokAPIError):
                _upload_video_chunks(
                    "https://upload.example.com",
                    mock_video_file,
                    os.path.getsize(mock_video_file),
                )


class TestCheckPublishStatus:
    """Tests for _check_publish_status function."""

    def test_successful_status_check(self, mock_access_token, mock_tiktok_status_response_success):
        """Should return status data on success."""
        with patch("tiktok.requests.post") as mock_post:
            mock_post.return_value.json.return_value = mock_tiktok_status_response_success

            result = _check_publish_status(mock_access_token, "test_publish_id")
            assert result["status"] == "PUBLISH_COMPLETE"

    def test_error_response(self, mock_access_token, mock_tiktok_error_response):
        """Should raise TikTokAPIError on error response."""
        with patch("tiktok.requests.post") as mock_post:
            mock_post.return_value.json.return_value = mock_tiktok_error_response

            with pytest.raises(tiktok.TikTokAPIError):
                _check_publish_status(mock_access_token, "test_publish_id")


class TestPostVideo:
    """Tests for the main post_video function."""

    def test_successful_post(
        self, env_with_token, mock_video_file,
        mock_tiktok_init_response, mock_tiktok_status_response_success,
    ):
        """Should successfully post a video and return result."""
        with patch("tiktok.requests.post") as mock_post, \
             patch("tiktok.requests.put") as mock_put:
            mock_post.return_value.json.side_effect = [
                mock_tiktok_init_response,
                mock_tiktok_status_response_success,
            ]
            mock_put.return_value.status_code = 200

            result = post_video(mock_video_file)

            assert result["success"] is True
            assert result["publish_id"] == "test_publish_id_12345"

    def test_post_with_provided_token(
        self, mock_video_file,
        mock_tiktok_init_response, mock_tiktok_status_response_success,
    ):
        """Should use provided access token instead of environment."""
        with patch("tiktok.requests.post") as mock_post, \
             patch("tiktok.requests.put") as mock_put:
            mock_post.return_value.json.side_effect = [
                mock_tiktok_init_response,
                mock_tiktok_status_response_success,
            ]
            mock_put.return_value.status_code = 200

            result = post_video(mock_video_file, access_token="custom_token")

            assert result["success"] is True

    def test_missing_token_raises_error(self, mock_video_file):
        """Should raise MissingTokenError when token not set."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(tiktok.MissingTokenError):
                post_video(mock_video_file)

    def test_file_not_found_raises_error(self, env_with_token):
        """Should raise FileNotFoundError for non-existent file."""
        with pytest.raises(FileNotFoundError):
            post_video("/nonexistent/path/video.mp4")


class TestExceptions:
    """Tests for exception classes."""

    def test_tiktok_api_error_message(self):
        """Should format error message correctly."""
        error = TikTokAPIError("test_code", "Test message")
        assert error.code == "test_code"
        assert error.message == "Test message"
        assert "test_code" in str(error)

    def test_missing_token_error_message(self):
        """Should include helpful message about setting token."""
        error = MissingTokenError()
        assert "TIKTOK_ACCESS_TOKEN" in str(error)

    def test_missing_oauth_config_error_message(self):
        """Should include helpful message about OAuth config."""
        error = MissingOAuthConfigError()
        assert "TIKTOK_CLIENT_KEY" in str(error)
