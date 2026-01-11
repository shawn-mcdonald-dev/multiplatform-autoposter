"""Unit tests for authentication and OAuth flow."""

import pytest
from unittest.mock import patch
from datetime import datetime, timedelta
from io import BytesIO

from fastapi.testclient import TestClient


class TestPasswordHashing:
    """Tests for password hashing utilities."""

    def test_hash_password_returns_hash(self):
        """Should return a bcrypt hash."""
        from auth import hash_password
        password = "test_password_123"
        hashed = hash_password(password)

        assert hashed != password
        assert hashed.startswith("$2b$")

    def test_verify_password_correct(self):
        """Should verify correct password."""
        from auth import hash_password, verify_password
        password = "test_password_123"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Should reject incorrect password."""
        from auth import hash_password, verify_password
        password = "test_password_123"
        hashed = hash_password(password)

        assert verify_password("wrong_password", hashed) is False


class TestJWT:
    """Tests for JWT token creation and validation."""

    def test_create_access_token(self):
        """Should create a valid JWT token."""
        from auth import create_access_token
        token = create_access_token(1, "testuser")

        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_access_token_valid(self):
        """Should decode valid token."""
        from auth import create_access_token, decode_access_token
        token = create_access_token(42, "testuser")
        payload = decode_access_token(token)

        assert int(payload["sub"]) == 42
        assert payload["username"] == "testuser"

    def test_decode_access_token_invalid(self):
        """Should raise HTTPException for invalid token."""
        from auth import decode_access_token
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            decode_access_token("invalid_token")
        assert exc_info.value.status_code == 401


class TestAuthEndpoints:
    """Tests for authentication API endpoints."""

    def test_register_success(self):
        """Should register a new user."""
        from main import app
        client = TestClient(app)

        with patch("main.get_user_by_username", return_value=None), \
             patch("main.create_user", return_value=1):
            response = client.post(
                "/auth/register",
                json={"username": "newuser", "password": "password123"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["username"] == "newuser"

    def test_register_duplicate_username(self):
        """Should reject duplicate username."""
        from main import app
        client = TestClient(app)

        with patch("main.get_user_by_username", return_value={"id": 1, "username": "existing"}):
            response = client.post(
                "/auth/register",
                json={"username": "existing", "password": "password123"},
            )

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    def test_login_success(self):
        """Should login with correct credentials."""
        from main import app
        from auth import hash_password
        client = TestClient(app)

        mock_user = {
            "id": 1,
            "username": "testuser",
            "password_hash": hash_password("password123"),
        }

        with patch("main.get_user_by_username", return_value=mock_user):
            response = client.post(
                "/auth/login",
                json={"username": "testuser", "password": "password123"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data

    def test_login_invalid_username(self):
        """Should reject invalid username."""
        from main import app
        client = TestClient(app)

        with patch("main.get_user_by_username", return_value=None):
            response = client.post(
                "/auth/login",
                json={"username": "nonexistent", "password": "password123"},
            )

        assert response.status_code == 401

    def test_get_me_authenticated(self):
        """Should return user info when authenticated."""
        from main import app
        from auth import create_access_token
        client = TestClient(app)

        token = create_access_token(1, "testuser")

        with patch("auth.get_user_by_id", return_value={"id": 1, "username": "testuser"}), \
             patch("main.has_tiktok_linked", return_value=True):
            response = client.get(
                "/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser"
        assert data["tiktok_linked"] is True

    def test_get_me_unauthenticated(self):
        """Should reject unauthenticated request."""
        from main import app
        client = TestClient(app)

        response = client.get("/auth/me")
        # 401 Unauthorized or 403 Forbidden are both valid
        assert response.status_code in (401, 403)


class TestTikTokOAuthEndpoints:
    """Tests for TikTok OAuth endpoints."""

    def test_tiktok_login_success(self):
        """Should return TikTok authorization URL."""
        from main import app
        from auth import create_access_token
        client = TestClient(app)

        token = create_access_token(1, "testuser")

        with patch("auth.get_user_by_id", return_value={"id": 1, "username": "testuser"}), \
             patch("main.get_authorization_url", return_value=("https://tiktok.com/auth?state=abc", "abc")):
            response = client.get(
                "/auth/tiktok/login",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200
        assert "authorization_url" in response.json()

    def test_tiktok_callback_success(self):
        """Should handle OAuth callback successfully."""
        from main import app, oauth_states
        from datetime import datetime
        client = TestClient(app)

        state = "test_state_123"
        oauth_states[state] = {"user_id": 1, "created_at": datetime.utcnow()}

        mock_token_data = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "expires_in": 3600,
        }

        with patch("main.exchange_code_for_token", return_value=mock_token_data), \
             patch("main.save_tiktok_tokens"):
            response = client.get(f"/auth/tiktok/callback?code=test_code&state={state}")

        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_tiktok_callback_invalid_state(self):
        """Should reject invalid state."""
        from main import app
        client = TestClient(app)

        response = client.get("/auth/tiktok/callback?code=test&state=invalid")
        assert response.status_code == 400


class TestUploadEndpointWithAuth:
    """Tests for authenticated upload endpoint."""

    def test_upload_unauthenticated(self, mock_video_bytes):
        """Should reject unauthenticated upload."""
        from main import app
        client = TestClient(app)

        response = client.post(
            "/upload",
            files={"file": ("test.mp4", BytesIO(mock_video_bytes), "video/mp4")},
        )
        # 401 Unauthorized or 403 Forbidden are both valid
        assert response.status_code in (401, 403)

    def test_upload_without_tiktok_linked(self, mock_video_bytes):
        """Should reject upload when TikTok not linked."""
        from main import app
        from auth import create_access_token
        client = TestClient(app)

        token = create_access_token(1, "testuser")

        with patch("auth.get_user_by_id", return_value={"id": 1, "username": "testuser"}), \
             patch("main.get_tiktok_tokens", return_value=None):
            response = client.post(
                "/upload",
                files={"file": ("test.mp4", BytesIO(mock_video_bytes), "video/mp4")},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 400
        assert "not linked" in response.json()["detail"]

    def test_upload_success(self, mock_video_bytes):
        """Should upload video when authenticated and TikTok linked."""
        from main import app
        from auth import create_access_token
        client = TestClient(app)

        token = create_access_token(1, "testuser")
        mock_tokens = {"access_token": "tiktok_token", "refresh_token": None, "expires_at": None}
        mock_result = {"success": True, "publish_id": "123", "status": "COMPLETE"}

        with patch("auth.get_user_by_id", return_value={"id": 1, "username": "testuser"}), \
             patch("main.get_tiktok_tokens", return_value=mock_tokens), \
             patch("main.post_video", return_value=mock_result), \
             patch("main.log_post"):
            response = client.post(
                "/upload",
                files={"file": ("test.mp4", BytesIO(mock_video_bytes), "video/mp4")},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200
        assert response.json()["status"] == "posted"


class TestHealthCheck:
    """Tests for health check endpoint."""

    def test_health_check(self):
        """Should return healthy status."""
        from main import app
        client = TestClient(app)

        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

