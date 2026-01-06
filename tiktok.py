"""TikTok Content Posting API integration."""

import os
import requests
from typing import Optional

TIKTOK_API_BASE = "https://open.tiktokapis.com"
CHUNK_SIZE = 10 * 1024 * 1024  # 10MB chunks for upload


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


def get_access_token() -> str:
    """Get the TikTok access token from environment.

    Returns:
        The access token string.

    Raises:
        MissingTokenError: If the token is not set.
    """
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


def _init_video_upload(token: str, file_size: int) -> dict:
    """Initialize a video upload with TikTok.

    Args:
        token: The access token.
        file_size: Size of the video file in bytes.

    Returns:
        Dict containing publish_id and upload_url.

    Raises:
        TikTokAPIError: If the API returns an error.
    """
    url = f"{TIKTOK_API_BASE}/v2/post/publish/video/init/"

    payload = {
        "post_info": {
            "title": "Video uploaded via Autoposter",
            "privacy_level": "SELF_ONLY",  # Safe default - creator can change on TikTok
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
    """Upload video file in chunks to TikTok.

    Args:
        upload_url: The upload URL from init response.
        file_path: Path to the video file.
        file_size: Total size of the file.

    Raises:
        TikTokAPIError: If upload fails.
    """
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
    """Check the status of a video publication.

    Args:
        token: The access token.
        publish_id: The publish ID from init response.

    Returns:
        Dict containing status information.

    Raises:
        TikTokAPIError: If the API returns an error.
    """
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


def post_video(file_path: str) -> dict:
    """Post a video to TikTok.

    This function handles the complete flow:
    1. Validates the access token exists
    2. Initializes the upload with TikTok
    3. Uploads the video file in chunks
    4. Checks and returns the publication status

    Args:
        file_path: Path to the video file to upload.

    Returns:
        Dict containing the publication result with status and publish_id.

    Raises:
        MissingTokenError: If access token is not configured.
        TikTokAPIError: If any API call fails.
        FileNotFoundError: If the video file doesn't exist.
    """
    # Validate token exists
    token = get_access_token()

    # Validate file exists
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Video file not found: {file_path}")

    file_size = os.path.getsize(file_path)

    # Step 1: Initialize upload
    init_data = _init_video_upload(token, file_size)
    publish_id = init_data["publish_id"]
    upload_url = init_data["upload_url"]

    # Step 2: Upload video chunks
    _upload_video_chunks(upload_url, file_path, file_size)

    # Step 3: Check status
    status_data = _check_publish_status(token, publish_id)

    return {
        "success": True,
        "publish_id": publish_id,
        "status": status_data.get("status", "UNKNOWN"),
    }
