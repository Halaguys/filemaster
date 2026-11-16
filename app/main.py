from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from PIL import Image
from pypdf import PdfReader, PdfWriter
import sqlite3, secrets, shutil, subprocess, os, re
from urllib.parse import urlparse
import yt_dlp

BASE = Path(__file__).resolve().parent
STATIC = BASE / "static"
TMP = BASE.parent / "tmp"
TMP.mkdir(exist_ok=True)
DB = BASE.parent / "links.db"

app = FastAPI(title="FileMaster")
app.mount("/static", StaticFiles(directory=STATIC), name="static")

def db():
    con = sqlite3.connect(DB)
    con.execute("CREATE TABLE IF NOT EXISTS links (code TEXT PRIMARY KEY, url TEXT NOT NULL)")
    return con

def safe_name(name: str) -> str:
    name = Path(name or "file").name
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)[:100] or "file"

def save_upload(upload: UploadFile) -> Path:
    suffix = Path(safe_name(upload.filename)).suffix
    path = TMP / f"{secrets.token_hex(12)}{suffix}"
    with path.open("wb") as f:
        shutil.copyfileobj(upload.file, f)
    return path

@app.get("/", response_class=HTMLResponse)
def home():
    return (STATIC / "index.html").read_text(encoding="utf-8")

@app.post("/api/pdf/compress")
async def compress_pdf(file: UploadFile = File(...)):
    src = save_upload(file)
    out = TMP / f"{src.stem}_optimized.pdf"
    try:
        reader = PdfReader(str(src))
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        writer.add_metadata({"/Producer": "FileMaster"})
        with out.open("wb") as f:
            writer.write(f)
        return FileResponse(out, filename="filemaster-compressed.pdf", media_type="application/pdf")
    except Exception as e:
        raise HTTPException(400, f"Could not process PDF: {e}")
    finally:
        src.unlink(missing_ok=True)

@app.post("/api/pdf/merge")
async def merge_pdf(files: list[UploadFile] = File(...)):
    if len(files) < 2:
        raise HTTPException(400, "Upload at least two PDF files.")
    out = TMP / f"{secrets.token_hex(8)}_merged.pdf"
    writer = PdfWriter()
    paths = []
    try:
        for f in files:
            p = save_upload(f); paths.append(p)
            reader = PdfReader(str(p))
            for page in reader.pages:
                writer.add_page(page)
        with out.open("wb") as dst:
            writer.write(dst)
        return FileResponse(out, filename="merged.pdf", media_type="application/pdf")
    except Exception as e:
        raise HTTPException(400, f"Could not merge PDFs: {e}")
    finally:
        for p in paths: p.unlink(missing_ok=True)

@app.post("/api/pdf/split")
async def split_pdf(file: UploadFile = File(...), pages: str = Form(...)):
    src = save_upload(file)
    out = TMP / f"{secrets.token_hex(8)}_split.pdf"
    try:
        reader = PdfReader(str(src))
        writer = PdfWriter()
        # User enters one-based pages/ranges, e.g. 1-3,5,8-9
        selected = set()
        for part in pages.split(","):
            part = part.strip()
            if "-" in part:
                a, b = [int(x.strip()) for x in part.split("-", 1)]
                selected.update(range(a, b + 1))
            elif part:
                selected.add(int(part))
        if not selected or min(selected) < 1 or max(selected) > len(reader.pages):
            raise HTTPException(400, f"Enter page numbers from 1 to {len(reader.pages)}.")
        for n in sorted(selected):
            writer.add_page(reader.pages[n - 1])
        with out.open("wb") as dst: writer.write(dst)
        return FileResponse(out, filename="split-pages.pdf", media_type="application/pdf")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Could not split PDF: {e}")
    finally:
        src.unlink(missing_ok=True)

@app.post("/api/image/resize")
async def resize_image(file: UploadFile = File(...), width: int = Form(0),
                       height: int = Form(0), quality: int = Form(80),
                       max_kb: int = Form(0), output: str = Form("jpg")):
    src = save_upload(file)
    ext = output.lower()
    if ext not in ("jpg", "png", "webp"): raise HTTPException(400, "Choose JPG, PNG or WebP.")
    out = TMP / f"{secrets.token_hex(8)}.{ext}"
    try:
        im = Image.open(src)
        im.load()
        im.thumbnail((width or im.width, height or im.height), Image.Resampling.LANCZOS)
        if ext == "jpg":
            if im.mode not in ("RGB", "L"): im = im.convert("RGB")
            im.save(out, "JPEG", quality=max(10, min(95, quality)), optimize=True)
        elif ext == "webp":
            im.save(out, "WEBP", quality=max(10, min(95, quality)), method=6)
        else:
            im.save(out, "PNG", optimize=True)
        # Best-effort target-size tuning for JPEG/WebP.
        if max_kb > 0 and ext in ("jpg", "webp") and out.stat().st_size > max_kb * 1024:
            q = max(10, min(90, quality))
            while out.stat().st_size > max_kb * 1024 and q > 10:
                q -= 5
                im.save(out, "JPEG" if ext == "jpg" else "WEBP", quality=q, optimize=True)
        media = {"jpg":"image/jpeg", "png":"image/png", "webp":"image/webp"}[ext]
        return FileResponse(out, filename=f"resized.{ext}", media_type=media)
    except Exception as e:
        raise HTTPException(400, f"Could not process image: {e}")
    finally:
        src.unlink(missing_ok=True)

@app.post("/api/media/download")
async def media_download(url: str = Form(...), kind: str = Form("mp4"), quality: str = Form("best")):
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise HTTPException(400, "Enter a valid public http(s) media URL.")
    if kind not in ("mp4", "mp3"): raise HTTPException(400, "Choose MP4 or MP3.")
    # No cookies, credentials, private links, DRM or access-control bypass.
    outtmpl = str(TMP / f"{secrets.token_hex(10)}.%(ext)s")
    if kind == "mp3":
        fmt = "bestaudio/best"
    elif quality == "2160":
        fmt = "bestvideo[height<=2160]+bestaudio/best[height<=2160]"
    elif quality == "1080":
        fmt = "bestvideo[height<=1080]+bestaudio/best[height<=1080]"
    elif quality == "720":
        fmt = "bestvideo[height<=720]+bestaudio/best[height<=720]"
    else:
        fmt = "bestvideo+bestaudio/best"
    opts = {
        "outtmpl": outtmpl, "format": fmt, "noplaylist": True,
        "quiet": True, "no_warnings": True, "restrictfilenames": True,
        "merge_output_format": "mp4",
        "max_filesize": 500 * 1024 * 1024,
    }
    if kind == "mp3":
        opts["postprocessors"] = [{"key":"FFmpegExtractAudio","preferredcodec":"mp3","preferredquality":"192"}]
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = Path(ydl.prepare_filename(info))
            if kind == "mp3": path = path.with_suffix(".mp3")
            elif path.suffix.lower() != ".mp4":
                candidate = path.with_suffix(".mp4")
                if candidate.exists(): path = candidate
            if not path.exists():
                matches = sorted(TMP.glob(path.stem + "*"), key=lambda p:p.stat().st_mtime, reverse=True)
                if matches: path = matches[0]
            if not path.exists(): raise RuntimeError("Output file was not created. Check FFmpeg and source support.")
            media = "audio/mpeg" if kind == "mp3" else "video/mp4"
            return FileResponse(path, filename=f"filemaster-download.{kind}", media_type=media)
    except Exception as e:
        raise HTTPException(400, f"Download failed: {str(e)[:300]}")

@app.post("/api/shorten")
async def shorten(url: str = Form(...)):
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise HTTPException(400, "Enter a valid http(s) URL.")
    code = secrets.token_urlsafe(5).replace("-", "").replace("_", "")[:7]
    con = db()
    con.execute("INSERT INTO links(code,url) VALUES(?,?)", (code, url.strip()))
    con.commit(); con.close()
    return {"short_url": f"/s/{code}"}

@app.get("/s/{code}")
def redirect_short(code: str):
    con = db()
    row = con.execute("SELECT url FROM links WHERE code=?", (code,)).fetchone()
    con.close()
    if not row: raise HTTPException(404, "Short link not found.")
    return RedirectResponse(row[0], status_code=307)
