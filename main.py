"""FastAPI application for autoposter-core."""

import os
import shutil
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, UploadFile, HTTPException, Depends, Query
from pydantic import BaseModel

from auth import hash_password, verify_password, create_access_token, get_current_user
from db import (
    log_post,
    create_user,
    get_user_by_username,
    save_tiktok_tokens,
    get_tiktok_tokens,
    has_tiktok_linked,
)
from tiktok import (
    post_video,
    get_authorization_url,
    exchange_code_for_token,
    TikTokAPIError,
    MissingOAuthConfigError,
)


UPLOADS_DIR = "uploads"

# Store OAuth state temporarily (in production, use Redis or database)
oauth_states: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler - runs on startup and shutdown."""
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    yield


app = FastAPI(
    title="Autoposter Core",
    description="Upload videos once, post to multiple platforms with OAuth authentication",
    version="0.2.0",
    lifespan=lifespan,
)


# Pydantic models
class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


class UserResponse(BaseModel):
    id: int
    username: str
    tiktok_linked: bool


class TikTokAuthResponse(BaseModel):
    authorization_url: str


# Auth endpoints
@app.post("/auth/register", response_model=AuthResponse)
async def register(request: RegisterRequest):
    """Register a new user account."""
    existing_user = get_user_by_username(request.username)
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")

    password_hash = hash_password(request.password)
    user_id = create_user(request.username, password_hash)
    token = create_access_token(user_id, request.username)

    return {
        "access_token": token,
        "token_type": "bearer",
        "username": request.username,
    }


@app.post("/auth/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    """Login and get JWT token."""
    user = get_user_by_username(request.username)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if not verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token(user["id"], user["username"])

    return {
        "access_token": token,
        "token_type": "bearer",
        "username": user["username"],
    }


@app.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get current user information."""
    return {
        "id": current_user["id"],
        "username": current_user["username"],
        "tiktok_linked": has_tiktok_linked(current_user["id"]),
    }


@app.get("/auth/tiktok/login", response_model=TikTokAuthResponse)
async def tiktok_login(current_user: dict = Depends(get_current_user)):
    """Get TikTok OAuth authorization URL."""
    try:
        auth_url, state = get_authorization_url()

        oauth_states[state] = {
            "user_id": current_user["id"],
            "created_at": datetime.utcnow(),
        }

        return {"authorization_url": auth_url}

    except MissingOAuthConfigError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/auth/tiktok/callback")
async def tiktok_callback(
    code: str = Query(..., description="Authorization code from TikTok"),
    state: str = Query(..., description="State parameter for CSRF protection"),
):
    """Handle TikTok OAuth callback."""
    if state not in oauth_states:
        raise HTTPException(status_code=400, detail="Invalid or expired state parameter")

    state_data = oauth_states.pop(state)
    user_id = state_data["user_id"]

    try:
        token_data = exchange_code_for_token(code)

        expires_at = None
        if token_data.get("expires_in"):
            expires_at = int(datetime.utcnow().timestamp()) + token_data["expires_in"]

        save_tiktok_tokens(
            user_id,
            token_data["access_token"],
            token_data.get("refresh_token"),
            expires_at,
        )

        return {"success": True, "message": "TikTok account linked successfully"}

    except TikTokAPIError as e:
        raise HTTPException(status_code=502, detail=f"Failed to link TikTok account: {e.message}")


# Upload endpoint
@app.post("/upload")
async def upload_video(
    file: UploadFile,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Upload a video file and post it to TikTok. Requires authentication."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    tokens = get_tiktok_tokens(current_user["id"])
    if not tokens:
        raise HTTPException(
            status_code=400,
            detail="TikTok account not linked. Please link your TikTok account first.",
        )

    path = os.path.join(UPLOADS_DIR, file.filename)

    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        result = post_video(path, access_token=tokens["access_token"])
        log_post(file.filename, "POSTED", "tiktok", str(result), current_user["id"])
        return {"status": "posted", "platform": "tiktok", "result": result}

    except TikTokAPIError as e:
        log_post(file.filename, "FAILED", "tiktok", str(e), current_user["id"])
        raise HTTPException(status_code=502, detail=f"TikTok API error: {e.message}")

    except Exception as e:
        log_post(file.filename, "FAILED", "tiktok", str(e), current_user["id"])
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
