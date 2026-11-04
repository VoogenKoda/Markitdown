"""
FastAPI Web Server for Microsoft MarkItDown Studio
==================================================
Supports:
  1. YouTube Transcriber (Speech, Subtitles & Timestamps)
  2. PDF to Markdown (PyMuPDF, MarkItDown & Tables)
  3. Image Analysis (EXIF Metadata & OCR via RapidOCR)

Run with:
    python app.py
Or:
    uvicorn app.py:app --reload --port 8000
"""

from __future__ import annotations

import io
import os
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from image_converter import ImageToMarkdownConverter
from pdf_converter import PdfToMarkdownConverter
from transcriber import YouTubeTranscriber, extract_video_id, parse_time_str

# Initialize app
app = FastAPI(
    title="MarkItDown Studio",
    description="Multifunktsionaalne Markdown konverter: YouTube kõne, PDF dokumendid ja piltide EXIF/OCR Microsoft MarkItDown baasil",
    version="2.0.0",
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "css"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "js"), exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

# Mount static files and templates
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Shared Converters
transcriber = YouTubeTranscriber()
pdf_converter = PdfToMarkdownConverter()
image_converter = ImageToMarkdownConverter()


# --- Pydantic Request Models ---
class InfoRequest(BaseModel):
    url: str = Field(..., description="YouTube video URL või video ID")


class TranscribeRequest(BaseModel):
    url: str = Field(..., description="YouTube video URL või video ID")
    language: Optional[str] = Field(None, description="Valitud keelekood (nt 'et', 'en', 'de')")
    timestamps_mode: str = Field(
        "interval",
        description="Ajatemplite režiim: 'interval', 'sentence' või 'none'",
    )
    interval_seconds: int = Field(30, ge=5, le=300, description="Intervalli pikkus sekundites")
    use_native_markitdown: bool = Field(False, description="Kasuta Microsoft MarkItDown algset teisendajat")


class BatchRequest(BaseModel):
    urls: List[str] = Field(..., description="Nimekiri YouTube URL-idest")
    language: Optional[str] = None
    timestamps_mode: str = "interval"
    interval_seconds: int = 30


# --- Routes ---
@app.get("/", response_class=HTMLResponse)
async def serve_index(request: Request):
    """Serve the single-page application UI."""
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "app": "Microsoft MarkItDown Studio",
        "features": ["youtube", "pdf", "images_exif_ocr"],
        "version": "2.0.0",
    }


# =========================================================================
# 🎬 1. YOUTUBE TRANSCRIBER ENDPOINTS
# =========================================================================

@app.post("/api/info")
async def get_video_info(req: InfoRequest):
    """Fetch video metadata and available subtitle languages quickly."""
    video_id = extract_video_id(req.url)
    if not video_id:
        raise HTTPException(status_code=400, detail="Sisestatud link ei ole kehtiv YouTube URL või video ID.")

    try:
        meta = transcriber.get_video_info(req.url)
        return {
            "success": True,
            "data": {
                "video_id": meta.video_id,
                "url": meta.url,
                "title": meta.title,
                "channel": meta.channel,
                "channel_url": meta.channel_url,
                "duration_seconds": meta.duration_seconds,
                "duration_formatted": meta.duration_formatted,
                "view_count": meta.view_count,
                "like_count": meta.like_count,
                "thumbnail": meta.thumbnail,
                "description": meta.description,
                "upload_date": meta.upload_date,
                "tags": meta.tags,
                "available_languages": meta.available_languages,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Video info laadimine ebaõnnestus: {str(e)}")


@app.post("/api/transcribe")
async def transcribe_video(req: TranscribeRequest):
    """Run transcription on the given YouTube URL."""
    video_id = extract_video_id(req.url)
    if not video_id:
        raise HTTPException(status_code=400, detail="Sisestatud link ei ole kehtiv YouTube URL.")

    try:
        result = transcriber.transcribe(
            url=req.url,
            language=req.language,
            timestamps_mode=req.timestamps_mode,
            interval_seconds=req.interval_seconds,
            use_native_markitdown=req.use_native_markitdown,
        )

        return {
            "success": True,
            "data": {
                "metadata": {
                    "video_id": result.metadata.video_id,
                    "url": result.metadata.url,
                    "title": result.metadata.title,
                    "channel": result.metadata.channel,
                    "channel_url": result.metadata.channel_url,
                    "duration_seconds": result.metadata.duration_seconds,
                    "duration_formatted": result.metadata.duration_formatted,
                    "view_count": result.metadata.view_count,
                    "thumbnail": result.metadata.thumbnail,
                    "upload_date": result.metadata.upload_date,
                },
                "markdown": result.markdown,
                "plain_text": result.plain_text,
                "srt": result.srt,
                "language": result.language,
                "word_count": result.word_count,
                "char_count": result.char_count,
                "reading_time_minutes": result.reading_time_minutes,
                "used_engine": result.used_engine,
                "segments": [
                    {"start": s.start, "duration": s.duration, "text": s.text}
                    for s in result.segments
                ],
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transkribeerimise viga: {str(e)}")


@app.post("/api/batch")
async def batch_transcribe(req: BatchRequest):
    """Transcribe a batch of videos sequentially."""
    if not req.urls:
        raise HTTPException(status_code=400, detail="URL nimekiri on tühi.")

    results: List[Dict[str, Any]] = []

    for url in req.urls[:20]:
        u = url.strip()
        if not u:
            continue
        try:
            res = transcriber.transcribe(
                url=u,
                language=req.language,
                timestamps_mode=req.timestamps_mode,
                interval_seconds=req.interval_seconds,
            )
            results.append({
                "url": u,
                "success": True,
                "title": res.metadata.title,
                "video_id": res.metadata.video_id,
                "word_count": res.word_count,
                "markdown": res.markdown,
                "plain_text": res.plain_text,
            })
        except Exception as e:
            results.append({
                "url": u,
                "success": False,
                "error": str(e),
            })

    return {"success": True, "count": len(results), "items": results}


# =========================================================================
# 📄 2. PDF TO MARKDOWN ENDPOINTS
# =========================================================================

@app.post("/api/convert/pdf")
async def convert_pdf(
    file: UploadFile = File(...),
    extract_tables: bool = Form(True),
    use_native_markitdown: bool = Form(False),
    ocr_scanned: bool = Form(True),
):
    """Convert an uploaded PDF file to structured Markdown."""
    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Üleslaaditud PDF fail on tühi.")

        result = pdf_converter.convert(
            file_input=content,
            filename=file.filename or "document.pdf",
            use_native_markitdown=use_native_markitdown,
            extract_tables=extract_tables,
            ocr_scanned=ocr_scanned,
        )

        return {
            "success": True,
            "data": {
                "metadata": {
                    "filename": result.metadata.filename,
                    "title": result.metadata.title,
                    "author": result.metadata.author,
                    "subject": result.metadata.subject,
                    "page_count": result.metadata.page_count,
                    "file_size_formatted": result.metadata.file_size_formatted,
                    "creation_date": result.metadata.creation_date,
                    "toc": result.metadata.toc,
                },
                "markdown": result.markdown,
                "plain_text": result.plain_text,
                "page_count": result.page_count,
                "word_count": result.word_count,
                "char_count": result.char_count,
                "reading_time_minutes": result.reading_time_minutes,
                "tables_count": result.tables_count,
                "used_engine": result.used_engine,
                "pages": [
                    {
                        "page_num": p.page_num,
                        "text": p.text,
                        "tables_count": len(p.tables),
                        "image_count": p.image_count,
                        "is_scanned": p.is_scanned,
                    }
                    for p in result.pages
                ],
                "structured": {
                    "is_document": result.structured_doc.is_document,
                    "document_type": result.structured_doc.document_type,
                    "key_values": result.structured_doc.key_values,
                    "tables": result.structured_doc.tables,
                    "spatial_lines": result.structured_doc.spatial_lines,
                    "json_data": result.structured_doc.json_data,
                },
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF teisendamise viga: {str(e)}")


@app.get("/api/demo/pdf")
async def demo_pdf():
    """Generate and return conversion of a synthetic PDF demo document."""
    try:
        import fitz
        doc = fitz.open()
        doc.set_metadata({
            "title": "MarkItDown Tehniline Ülevaade 2026",
            "author": "Antigravity Research Lab",
            "subject": "PDF ja OCR teisendamine",
            "creator": "PyMuPDF Table Engine",
        })
        page = doc.new_page()
        page.insert_text((50, 60), "MarkItDown Dokumenditeisendus", fontsize=18)
        page.insert_text((50, 90), "See on näidisdokument, mis demonstreerib PDF-i teisendamist puhtaks Markdowniks.", fontsize=11)
        page.insert_text((50, 110), "Automaatselt eraldatakse metaandmed, pealkirjad, lõigud ja tabelid.", fontsize=11)

        # Draw a clear table with grid lines
        page.draw_rect(fitz.Rect(50, 140, 500, 240), color=(0.4, 0.4, 0.9), width=1)
        page.draw_line(fitz.Point(50, 175), fitz.Point(500, 175), color=(0.4, 0.4, 0.9), width=1)
        page.draw_line(fitz.Point(50, 205), fitz.Point(500, 205), color=(0.4, 0.4, 0.9), width=1)
        page.draw_line(fitz.Point(170, 140), fitz.Point(170, 240), color=(0.4, 0.4, 0.9), width=1)
        page.draw_line(fitz.Point(330, 140), fitz.Point(330, 240), color=(0.4, 0.4, 0.9), width=1)

        page.insert_text((60, 165), "Komponent", fontsize=11)
        page.insert_text((180, 165), "Tehnoloogia", fontsize=11)
        page.insert_text((340, 165), "Eelis", fontsize=11)

        page.insert_text((60, 195), "YouTube", fontsize=10)
        page.insert_text((180, 195), "yt-dlp & Whisper/Google", fontsize=10)
        page.insert_text((340, 195), "Ajatemplitega konspekt", fontsize=10)

        page.insert_text((60, 225), "PDF", fontsize=10)
        page.insert_text((180, 225), "PyMuPDF & MarkItDown", fontsize=10)
        page.insert_text((340, 225), "Tabelite tuvastus & OCR", fontsize=10)

        page.insert_text((50, 270), "Kokkuvõte:", fontsize=13)
        page.insert_text((50, 295), "MarkItDown muudab eri formaatides dokumendid LLM-valmis tekstiks.", fontsize=11)

        pdf_bytes = doc.tobytes()
        doc.close()

        result = pdf_converter.convert(pdf_bytes, filename="naidis_raport.pdf")
        return {
            "success": True,
            "data": {
                "metadata": {
                    "filename": result.metadata.filename,
                    "title": result.metadata.title,
                    "author": result.metadata.author,
                    "subject": result.metadata.subject,
                    "page_count": result.metadata.page_count,
                    "file_size_formatted": result.metadata.file_size_formatted,
                    "creation_date": result.metadata.creation_date,
                    "toc": result.metadata.toc,
                },
                "markdown": result.markdown,
                "plain_text": result.plain_text,
                "page_count": result.page_count,
                "word_count": result.word_count,
                "char_count": result.char_count,
                "reading_time_minutes": result.reading_time_minutes,
                "tables_count": result.tables_count,
                "used_engine": result.used_engine,
                "pages": [
                    {
                        "page_num": p.page_num,
                        "text": p.text,
                        "tables_count": len(p.tables),
                        "image_count": p.image_count,
                        "is_scanned": p.is_scanned,
                    }
                    for p in result.pages
                ],
                "structured": {
                    "is_document": result.structured_doc.is_document,
                    "document_type": result.structured_doc.document_type,
                    "key_values": result.structured_doc.key_values,
                    "tables": result.structured_doc.tables,
                    "spatial_lines": result.structured_doc.spatial_lines,
                    "json_data": result.structured_doc.json_data,
                },
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Näidis-PDF genereerimise viga: {str(e)}")


# =========================================================================
# 🖼️ 3. IMAGES (EXIF & OCR) ENDPOINTS
# =========================================================================

@app.post("/api/convert/image")
async def convert_image(
    file: UploadFile = File(...),
    run_ocr: bool = Form(True),
    extract_exif: bool = Form(True),
):
    """Convert an uploaded Image file: extract EXIF metadata and perform OCR."""
    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Üleslaaditud pildifail on tühi.")

        result = image_converter.convert(
            image_input=content,
            filename=file.filename or "image.jpg",
            run_ocr=run_ocr,
            extract_exif=extract_exif,
        )

        return {
            "success": True,
            "data": {
                "metadata": {
                    "filename": result.metadata.filename,
                    "format": result.metadata.format,
                    "mode": result.metadata.mode,
                    "width": result.metadata.width,
                    "height": result.metadata.height,
                    "megapixels": result.metadata.megapixels,
                    "aspect_ratio": result.metadata.aspect_ratio,
                    "file_size_formatted": result.metadata.file_size_formatted,
                    "camera": {
                        "make": result.metadata.camera.make,
                        "model": result.metadata.camera.model,
                        "lens_model": result.metadata.camera.lens_model,
                        "software": result.metadata.camera.software,
                        "exposure_time": result.metadata.camera.exposure_time,
                        "f_number": result.metadata.camera.f_number,
                        "iso": result.metadata.camera.iso,
                        "focal_length": result.metadata.camera.focal_length,
                        "focal_length_35mm": result.metadata.camera.focal_length_35mm,
                        "flash": result.metadata.camera.flash,
                        "datetime_original": result.metadata.camera.datetime_original,
                    },
                    "gps": {
                        "has_gps": result.metadata.gps.has_gps,
                        "latitude": result.metadata.gps.latitude,
                        "longitude": result.metadata.gps.longitude,
                        "altitude_meters": result.metadata.gps.altitude_meters,
                        "latitude_dms": result.metadata.gps.latitude_dms,
                        "longitude_dms": result.metadata.gps.longitude_dms,
                        "google_maps_url": result.metadata.gps.google_maps_url,
                    },
                    "raw_exif": result.metadata.raw_exif,
                },
                "markdown": result.markdown,
                "plain_text": result.plain_text,
                "word_count": result.word_count,
                "char_count": result.char_count,
                "ocr_engine": result.ocr_engine,
                "has_text": result.has_text,
                "ocr_blocks": [
                    {"text": b.text, "confidence": b.confidence}
                    for b in result.ocr_blocks
                ],
                "structured": {
                    "is_document": result.structured_doc.is_document,
                    "document_type": result.structured_doc.document_type,
                    "key_values": result.structured_doc.key_values,
                    "tables": result.structured_doc.tables,
                    "spatial_lines": result.structured_doc.spatial_lines,
                    "json_data": result.structured_doc.json_data,
                },
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pildi teisendamise viga: {str(e)}")


@app.get("/api/demo/image")
async def demo_image():
    """Generate and return conversion of a synthetic demo image with invoice, text & EXIF."""
    try:
        from PIL import Image, ImageDraw, ExifTags
        img = Image.new("RGB", (760, 320), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        # Left column (Seller & Address)
        draw.text((30, 25), "Veebimajutus / VoogenKoda OU (17360197)", fill=(15, 23, 42))
        draw.text((30, 52), "Oktaavia-5, 86003, Treimani", fill=(71, 85, 105))
        draw.text((30, 78), "IBAN: EE123456789012345678", fill=(71, 85, 105))

        # Right column (Invoice details)
        draw.text((450, 25), "Arve number: 4746666", fill=(15, 23, 42))
        draw.text((450, 52), "Viitenumber: 3031005", fill=(15, 23, 42))
        draw.text((450, 78), "Kuupaev: 30.10.2026", fill=(71, 85, 105))
        draw.text((450, 104), "Maksetahtaeg: 06.11.2026", fill=(71, 85, 105))
        draw.text((450, 130), "Viivis: 0,15% paevas", fill=(71, 85, 105))

        # Table header
        draw.text((30, 175), "Kirjeldus", fill=(15, 23, 42))
        draw.text((230, 175), "Periood", fill=(15, 23, 42))
        draw.text((450, 175), "Teenus", fill=(15, 23, 42))
        draw.text((630, 175), "Summa", fill=(15, 23, 42))

        # Table row
        draw.text((30, 210), "voogenkoda.ee", fill=(71, 85, 105))
        draw.text((230, 210), "06.11.2026-06.11.2027", fill=(71, 85, 105))
        draw.text((450, 210), "Domeeni pikendamine", fill=(71, 85, 105))
        draw.text((630, 210), "15.00 EUR", fill=(16, 185, 129))

        exif = img.getexif()
        exif[ExifTags.Base.Make] = "Sony"
        exif[ExifTags.Base.Model] = "ILCE-7RM5 (Alpha 7R V)"
        exif[ExifTags.Base.Software] = "MarkItDown Studio v2.0"

        buf = io.BytesIO()
        img.save(buf, format="JPEG", exif=exif)

        result = image_converter.convert(buf.getvalue(), filename="naidis_arve_voogenkoda.jpg")

        # Set rich demo camera & GPS specs
        result.metadata.camera.make = "Sony"
        result.metadata.camera.model = "ILCE-7RM5 (Alpha 7R V)"
        result.metadata.camera.lens_model = "FE 35mm F1.4 GM"
        result.metadata.camera.software = "MarkItDown Studio v2.0"
        result.metadata.camera.datetime_original = "2026-10-30 14:15:00"
        result.metadata.camera.exposure_time = "1/250s"
        result.metadata.camera.f_number = "f/2.8"
        result.metadata.camera.iso = "ISO 100"
        result.metadata.camera.focal_length = "35mm"
        result.metadata.camera.focal_length_35mm = "35mm (35mm ekv)"
        result.metadata.camera.flash = "Ei töötanud"

        result.metadata.gps.has_gps = True
        result.metadata.gps.latitude = 59.4370
        result.metadata.gps.longitude = 24.7536
        result.metadata.gps.altitude_meters = 35.0
        result.metadata.gps.latitude_dms = "59° 26' 13.20\" N"
        result.metadata.gps.longitude_dms = "24° 45' 12.96\" E"
        result.metadata.gps.google_maps_url = "https://www.google.com/maps?q=59.437,24.7536"

        result.markdown = image_converter._generate_markdown(
            result.metadata, result.ocr_blocks, result.plain_text, result.ocr_engine, result.structured_doc
        )

        return {
            "success": True,
            "data": {
                "metadata": {
                    "filename": result.metadata.filename,
                    "format": result.metadata.format,
                    "mode": result.metadata.mode,
                    "width": result.metadata.width,
                    "height": result.metadata.height,
                    "megapixels": result.metadata.megapixels,
                    "aspect_ratio": result.metadata.aspect_ratio,
                    "file_size_formatted": result.metadata.file_size_formatted,
                    "camera": {
                        "make": result.metadata.camera.make,
                        "model": result.metadata.camera.model,
                        "lens_model": result.metadata.camera.lens_model,
                        "software": result.metadata.camera.software,
                        "exposure_time": result.metadata.camera.exposure_time,
                        "f_number": result.metadata.camera.f_number,
                        "iso": result.metadata.camera.iso,
                        "focal_length": result.metadata.camera.focal_length,
                        "focal_length_35mm": result.metadata.camera.focal_length_35mm,
                        "flash": result.metadata.camera.flash,
                        "datetime_original": result.metadata.camera.datetime_original,
                    },
                    "gps": {
                        "has_gps": True,
                        "latitude": 59.4370,
                        "longitude": 24.7536,
                        "altitude_meters": 35.0,
                        "latitude_dms": "59° 26' 13.20\" N",
                        "longitude_dms": "24° 45' 12.96\" E",
                        "google_maps_url": "https://www.google.com/maps?q=59.437,24.7536",
                    },
                    "raw_exif": result.metadata.raw_exif,
                },
                "markdown": result.markdown,
                "plain_text": result.plain_text,
                "word_count": result.word_count,
                "char_count": result.char_count,
                "ocr_engine": result.ocr_engine,
                "has_text": result.has_text,
                "ocr_blocks": [
                    {"text": b.text, "confidence": b.confidence}
                    for b in result.ocr_blocks
                ],
                "structured": {
                    "is_document": result.structured_doc.is_document,
                    "document_type": result.structured_doc.document_type,
                    "key_values": result.structured_doc.key_values,
                    "tables": result.structured_doc.tables,
                    "spatial_lines": result.structured_doc.spatial_lines,
                    "json_data": result.structured_doc.json_data,
                },
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Näidispildi genereerimise viga: {str(e)}")


def start():
    """Entry point when running python app.py"""
    print("\n" + "=" * 65)
    print("🚀 Microsoft MarkItDown Studio (YouTube, PDF & Images) käivitub!")
    print("🌐 Ava veebibrauseris: http://localhost:8000")
    print("=" * 65 + "\n")
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    start()
