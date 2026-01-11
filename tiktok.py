"""TikTok Content Posting API integration."""

import os
import secrets
import requests
from typing import Optional
from urllib.parse import urlencode

TIKTOK_API_BASE = "https://open.tiktokapis.com"
TIKTOK_AUTH_BASE = "https://www.tiktok.com/v2/auth/authorize"
CHUNK_SIZE = 10 * 1024 * 1024  # 10MB chunks for upload

# OAuth configuration from environment
TIKTOK_CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY")
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET")
TIKTOK_REDIRECT_URI = os.getenv("TIKTOK_REDIRECT_URI", "http://localhost:8000/auth/tiktok/callback")


class TikTokAPIError(Exception):
    """Custom exception for TikTok API errors."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"TikTok API Error [{code}]: {message}")


class MissingTokenError(Exception):
    """Exception raised when access token is not configured."""

    def __init__(self):
        super().__init__(
            "TIKTOK_ACCESS_TOKEN environment variable is not set. "
            "Please set it with your TikTok API access token."
        )


class MissingOAuthConfigError(Exception):
    """Exception raised when OAuth configuration is missing."""

    def __init__(self):
        super().__init__(
            "TikTok OAuth configuration is incomplete. "
            "Please set TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, and TIKTOK_REDIRECT_URI."
        )


def get_access_token() -> str:
    """Get the TikTok access token from environment."""
    token = os.getenv("TIKTOK_ACCESS_TOKEN")
    if not token:
        raise MissingTokenError()
    return token


def _get_auth_headers(token: str) -> dict:
    """Get authorization headers for API requests."""
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=UTF-8",
    }


def get_authorization_url() -> tuple[str, str]:
    """Generate TikTok OAuth authorization URL.

    Returns:
        Tuple of (authorization_url, state) where state is used for CSRF protection.

    Raises:
        MissingOAuthConfigError: If OAuth credentials are not configured.
    """
    if not TIKTOK_CLIENT_KEY or not TIKTOK_REDIRECT_URI:
        raise MissingOAuthConfigError()

    state = secrets.token_urlsafe(32)

    params = {
        "client_key": TIKTOK_CLIENT_KEY,
        "scope": "user.info.basic,video.upload,video.publish",
        "response_type": "code",
        "redirect_uri": TIKTOK_REDIRECT_URI,
        "state": state,
    }

    auth_url = f"{TIKTOK_AUTH_BASE}/?{urlencode(params)}"
    return auth_url, state


def exchange_code_for_token(code: str) -> dict:
    """Exchange authorization code for access token.

    Args:
        code: The authorization code from TikTok callback.

    Returns:
        Dict containing access_token, refresh_token, expires_in, etc.

    Raises:
        MissingOAuthConfigError: If OAuth credentials are not configured.
        TikTokAPIError: If token exchange fails.
    """
    if not TIKTOK_CLIENT_KEY or not TIKTOK_CLIENT_SECRET:
        raise MissingOAuthConfigError()

    url = f"{TIKTOK_API_BASE}/v2/oauth/token/"

    payload = {
        "client_key": TIKTOK_CLIENT_KEY,
        "client_secret": TIKTOK_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": TIKTOK_REDIRECT_URI,
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    response = requests.post(url, data=payload, headers=headers)
    data = response.json()

    if "error" in data or response.status_code != 200:
        error_msg = data.get("error_description", data.get("message", "Token exchange failed"))
        raise TikTokAPIError(
            data.get("error", "token_exchange_failed"),
            error_msg,
        )

    return {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token"),
        "expires_in": data.get("expires_in"),
        "token_type": data.get("token_type"),
    }


def _init_video_upload(token: str, file_size: int) -> dict:
    """Initialize a video upload with TikTok."""
    url = f"{TIKTOK_API_BASE}/v2/post/publish/video/init/"

    payload = {
        "post_info": {
            "title": "Video uploaded via Autoposter",
            "privacy_level": "SELF_ONLY",
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": file_size,
            "chunk_size": CHUNK_SIZE,
            "total_chunk_count": (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE,
        },
    }

    response = requests.post(url, json=payload, headers=_get_auth_headers(token))
    data = response.json()

    if data.get("error", {}).get("code") != "ok":
        error = data.get("error", {})
        raise TikTokAPIError(
            error.get("code", "unknown"),
            error.get("message", "Unknown error occurred"),
        )

    return data["data"]


def _upload_video_chunks(upload_url: str, file_path: str, file_size: int) -> None:
    """Upload video file in chunks to TikTok."""
    with open(file_path, "rb") as f:
        chunk_index = 0
        offset = 0

        while offset < file_size:
            chunk = f.read(CHUNK_SIZE)
            chunk_end = min(offset + len(chunk), file_size)

            headers = {
                "Content-Type": "video/mp4",
                "Content-Length": str(len(chunk)),
                "Content-Range": f"bytes {offset}-{chunk_end - 1}/{file_size}",
            }

            response = requests.put(upload_url, data=chunk, headers=headers)

            if response.status_code not in (200, 201, 206):
                raise TikTokAPIError(
                    "upload_failed",
                    f"Chunk {chunk_index} upload failed with status {response.status_code}",
                )

            offset = chunk_end
            chunk_index += 1


def _check_publish_status(token: str, publish_id: str) -> dict:
    """Check the status of a video publication."""
    url = f"{TIKTOK_API_BASE}/v2/post/publish/status/fetch/"

    payload = {"publish_id": publish_id}

    response = requests.post(url, json=payload, headers=_get_auth_headers(token))
    data = response.json()

    if data.get("error", {}).get("code") != "ok":
        error = data.get("error", {})
        raise TikTokAPIError(
            error.get("code", "unknown"),
            error.get("message", "Unknown error occurred"),
        )

    return data["data"]


def post_video(file_path: str, access_token: Optional[str] = None) -> dict:
    """Post a video to TikTok.

    Args:
        file_path: Path to the video file to upload.
        access_token: Optional access token. If not provided, reads from environment.

    Returns:
        Dict containing the publication result with status and publish_id.

    Raises:
        MissingTokenError: If access token is not configured.
        TikTokAPIError: If any API call fails.
        FileNotFoundError: If the video file doesn't exist.
    """
    if access_token is None:
        token = get_access_token()
    else:
        token = access_token

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Video file not found: {file_path}")

    file_size = os.path.getsize(file_path)

    init_data = _init_video_upload(token, file_size)
    publish_id = init_data["publish_id"]
    upload_url = init_data["upload_url"]

    _upload_video_chunks(upload_url, file_path, file_size)

    status_data = _check_publish_status(token, publish_id)

    return {
        "success": True,
        "publish_id": publish_id,
        "status": status_data.get("status", "UNKNOWN"),
    }
