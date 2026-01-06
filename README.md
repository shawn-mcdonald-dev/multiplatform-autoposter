# Autoposter Core

A multiplatform autoposter for content creators. Upload your video once, and it automatically posts to multiple platforms.

## Features

- Upload videos via REST API
- Automatic posting to TikTok
- Database logging of all posts
- Simple and minimal design

## Prerequisites

1. **Python 3.11+**
2. **uv** - Install with:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
3. **TikTok Developer Account**:
   - Register at [developers.tiktok.com](https://developers.tiktok.com)
   - Create an app with "Content Posting API" permissions
   - Obtain an access token with `video.upload` and `video.publish` scopes

## Quick Start

```bash
# Clone and enter the project
cd autoposter-core

# Install dependencies
uv sync

# Set your TikTok access token
export TIKTOK_ACCESS_TOKEN="your_token_here"

# Start the server
uv run uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`.

## API Endpoints

### Upload Video

**POST** `/upload`

Upload a video file to be posted to TikTok.

```bash
curl -X POST "http://localhost:8000/upload" \
  -F "file=@your_video.mp4"
```

**Response (success):**
```json
{
  "status": "posted",
  "platform": "tiktok"
}
```

**Response (failure):**
```json
{
  "status": "failed",
  "error": "Error message here"
}
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TIKTOK_ACCESS_TOKEN` | Yes | Your TikTok API access token |

## Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage report
uv run pytest --cov=. --cov-report=term-missing

# Run specific test file
uv run pytest tests/test_tiktok.py
```

## Project Structure

```
autoposter-core/
├── main.py           # FastAPI application
├── tiktok.py         # TikTok API integration
├── db.py             # Database logging
├── uploads/          # Uploaded video files
├── posts.db          # SQLite database
├── pyproject.toml    # Project configuration
└── tests/
    ├── conftest.py   # Test fixtures
    ├── test_main.py  # API endpoint tests
    ├── test_tiktok.py# TikTok integration tests
    └── test_db.py    # Database tests
```

## Video Requirements

- **Max size**: 4GB
- **Formats**: mp4, webm, mov
- **Duration**: 3 seconds - 10 minutes

## License

MIT

