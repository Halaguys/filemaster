# FileMaster — PDF, image, media and link tools

A starter web application with a responsive frontend and a FastAPI backend.

## Included
- PDF merge, split and rewrite/compress endpoint
- Image resize and compression with target dimensions / quality
- Public media URL processing through yt-dlp for content the user owns or is authorized to download
- MP4/MP3 output selection and best-available quality selection (source-dependent)
- Basic URL shortener (SQLite)
- Drag-and-drop upload UI and adjustable size controls

## Run locally
1. Install Python 3.10+.
2. (Recommended) Create and activate a virtual environment.
3. Install dependencies:
   `pip install -r requirements.txt`
4. Start:
   `uvicorn app.main:app --reload`
5. Open http://127.0.0.1:8000

For video/audio processing, install FFmpeg and ensure `ffmpeg` is on PATH.
PDF rewrite may reduce some files slightly; meaningful PDF image optimization may require Ghostscript.
The app does not bypass DRM, paywalls, private-account restrictions, login walls, or other access controls.
Only process media you own or have permission to download. Respect each platform's terms and copyright law.

## Production notes
- Put the app behind HTTPS and a reverse proxy.
- Add authentication, per-user quotas, rate limiting, malware scanning, and job queueing before public launch.
- Configure temporary file cleanup and storage limits.
- Use object storage for large files; do not rely on local temp storage at scale.
- Link shortener currently stores URLs in a local SQLite database. Add abuse reporting, rate limits, and domain safety checks before public launch.
- Video source availability and resolution depend on the platform, source, and yt-dlp support. 4K is not guaranteed.
