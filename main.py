"""FastAPI application for autoposter-core."""

import os
import shutil
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, HTTPException

from db import log_post
from tiktok import post_video, MissingTokenError, TikTokAPIError


UPLOADS_DIR = "uploads"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler - runs on startup and shutdown."""
    # Startup: ensure uploads directory exists
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    yield
    # Shutdown: nothing to clean up


app = FastAPI(
    title="Autoposter Core",
    description="Upload videos once, post to multiple platforms",
    version="0.1.0",
    lifespan=lifespan,
)


@app.post("/upload")
async def upload_video(file: UploadFile) -> dict:
    """Upload a video file and post it to TikTok.

    Args:
        file: The video file to upload.

    Returns:
        Dict with status and platform information.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    path = os.path.join(UPLOADS_DIR, file.filename)

    # Save uploaded file
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        result = post_video(path)
        log_post(file.filename, "POSTED", "tiktok", str(result))
        return {"status": "posted", "platform": "tiktok", "result": result}

    except MissingTokenError as e:
        log_post(file.filename, "FAILED", "tiktok", str(e))
        raise HTTPException(
            status_code=500,
            detail="TikTok access token not configured. Set TIKTOK_ACCESS_TOKEN environment variable.",
        )

    except TikTokAPIError as e:
        log_post(file.filename, "FAILED", "tiktok", str(e))
        raise HTTPException(
            status_code=502,
            detail=f"TikTok API error: {e.message}",
        )

    except Exception as e:
        log_post(file.filename, "FAILED", "tiktok", str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(e)}",
        )
