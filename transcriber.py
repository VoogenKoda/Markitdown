"""
YouTube Transcriber based on Microsoft MarkItDown
=================================================
A flexible, high-performance YouTube transcription and markdown converter engine
leveraging Microsoft MarkItDown, yt-dlp, and YouTube Transcript API.
"""

from __future__ import annotations

import io
import json
import logging
import math
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

import yt_dlp
from markitdown import MarkItDown
from markitdown._base_converter import DocumentConverter, DocumentConverterResult
from markitdown._stream_info import StreamInfo

# Configure logger
logger = logging.getLogger("YouTubeTranscriber")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Ensure ffmpeg from imageio_ffmpeg is recognized if installed
try:
    import imageio_ffmpeg

    FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG_EXE = shutil.which("ffmpeg")


def find_valid_cookie_file() -> Optional[str]:
    """
    Finds a valid cookies.txt file that contains actual cookie entries (not just comments).
    Also supports raw cookie content via YOUTUBE_COOKIES_CONTENT env var.
    """
    raw_content = os.environ.get("YOUTUBE_COOKIES_CONTENT")
    if raw_content and raw_content.strip():
        tmp_cookie_path = os.path.join(tempfile.gettempdir(), "yt_env_cookies.txt")
        try:
            with open(tmp_cookie_path, "w", encoding="utf-8") as f:
                f.write(raw_content.strip() + "\n")
            return tmp_cookie_path
        except Exception as e:
            logger.warning(f"Ei saanud YOUTUBE_COOKIES_CONTENT faili kirjutada: {e}")

    cookie_candidates = [
        os.environ.get("YOUTUBE_COOKIES_FILE"),
        "data/cookies.txt",
        "/app/data/cookies.txt",
        "cookies.txt",
        "/app/cookies.txt",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt"),
    ]
    for cp in cookie_candidates:
        if cp and os.path.isfile(cp):
            try:
                with open(cp, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                valid_lines = [l for l in content.splitlines() if l.strip() and not l.strip().startswith("#")]
                if valid_lines:
                    return cp
            except Exception:
                continue
    return None


def get_yt_dlp_common_opts() -> Dict[str, Any]:
    """
    Common yt-dlp options configured with mobile client spoofing (Android/iOS)
    to bypass YouTube datacenter bot verification, with automatic cookies and proxy support.
    """
    opts: Dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 20,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios", "mweb", "web"],
            }
        },
    }

    # Automatically enable Node.js runtime and remote challenge solver if available
    if shutil.which("node"):
        opts["js_runtimes"] = {"node": {}}
        opts["remote_components"] = ["ejs:github"]

    # Automatically check for proxy
    proxy = os.environ.get("YOUTUBE_PROXY") or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
    if proxy:
        opts["proxy"] = proxy
        logger.info(f"Kasutatakse YouTube proxy't: {proxy}")

    # Automatically check for cookies.txt
    cookie_file = find_valid_cookie_file()
    if cookie_file:
        opts["cookiefile"] = cookie_file
        logger.info(f"Kasutatakse YouTube küpsiseid: {cookie_file}")

    return opts


@dataclass
class TranscriptSegment:
    """Represents a single snippet of a transcript with timing."""
    start: float  # Start time in seconds
    duration: float  # Duration in seconds
    text: str  # Clean transcribed text

    @property
    def end(self) -> float:
        return self.start + self.duration


@dataclass
class VideoMetadata:
    """Metadata extracted for a YouTube video."""
    video_id: str
    url: str
    title: str = "Tundmatu video"
    channel: str = "Teadmata autor"
    channel_url: str = ""
    duration_seconds: int = 0
    duration_formatted: str = "00:00"
    view_count: int = 0
    like_count: int = 0
    thumbnail: str = ""
    description: str = ""
    upload_date: str = ""
    tags: List[str] = field(default_factory=list)
    available_languages: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class TranscriptionResult:
    """Complete result returned by the transcriber."""
    metadata: VideoMetadata
    markdown: str
    plain_text: str
    srt: str
    segments: List[TranscriptSegment]
    language: str
    word_count: int
    char_count: int
    reading_time_minutes: int
    used_engine: str  # 'markitdown_native', 'enhanced_timedtext', 'audio_fallback'


def format_seconds(seconds: float, include_hours: bool = False) -> str:
    """Format seconds into MM:SS or HH:MM:SS string."""
    seconds = max(0.0, seconds)
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    if hours > 0 or include_hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_srt_timestamp(seconds: float) -> str:
    """Format seconds into SubRip timestamp: HH:MM:SS,mmm"""
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def parse_time_str(val: Any) -> float:
    """
    Parse time string like '01:15', '1:15', '01:15:30', or '75' into seconds (float).
    Supports int, float, or string.
    """
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return max(0.0, float(val))
    val_str = str(val).strip()
    if not val_str:
        return 0.0
    try:
        if ":" in val_str:
            parts = val_str.split(":")
            if len(parts) == 2:
                mins, secs = parts
                return max(0.0, int(mins) * 60.0 + float(secs))
            elif len(parts) == 3:
                hrs, mins, secs = parts
                return max(0.0, int(hrs) * 3600.0 + int(mins) * 60.0 + float(secs))
        return max(0.0, float(val_str))
    except (ValueError, TypeError):
        return 0.0


def extract_video_id(url: str) -> Optional[str]:
    """
    Robust extraction of 11-character YouTube video ID from various URL patterns:
    - https://www.youtube.com/watch?v=dQw4w9WgXcQ
    - https://youtu.be/dQw4w9WgXcQ
    - https://www.youtube.com/shorts/dQw4w9WgXcQ
    - https://www.youtube.com/embed/dQw4w9WgXcQ
    - https://www.youtube.com/live/dQw4w9WgXcQ
    - Raw ID: dQw4w9WgXcQ
    """
    if not url:
        return None
    url = url.strip()

    # Raw 11-char ID
    if re.fullmatch(r"^[a-zA-Z0-9_-]{11}$", url):
        return url

    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()

    if hostname in {"youtu.be", "www.youtu.be"}:
        path = parsed.path.strip("/")
        return path.split("/")[0] if path else None

    if hostname in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        if parts:
            if parts[0] == "watch":
                params = parse_qs(parsed.query)
                return params.get("v", [None])[0]
            if parts[0] in {"shorts", "embed", "live", "v"}:
                return parts[1] if len(parts) > 1 else None

    # Fallback regex search anywhere in the string
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
    if match:
        return match.group(1)

    return None


class YouTubeTranscriber:
    """
    Main transcription engine built on Microsoft MarkItDown.
    Supports subtitle timedtext extraction, paragraph structuring,
    multi-language selection, SRT exports, and audio fallback.
    """

    def __init__(self):
        self.md_native = MarkItDown()

    def get_video_info(self, url: str) -> VideoMetadata:
        """Fetch video metadata and list of available transcript languages."""
        video_id = extract_video_id(url)
        if not video_id:
            raise ValueError(f"Vigane YouTube URL või video ID: '{url}'")

        standard_url = f"https://www.youtube.com/watch?v={video_id}"

        ydl_opts = get_yt_dlp_common_opts()
        ydl_opts.update({
            "skip_download": True,
            "extract_flat": False,
        })

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(standard_url, download=False) or {}
        except Exception as e:
            logger.warning(f"yt-dlp extract_info viga: {e}. Tagastame põhiandmed.")
            return VideoMetadata(
                video_id=video_id,
                url=standard_url,
                title=f"YouTube Video ({video_id})",
                thumbnail=f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
            )

        duration_sec = int(info.get("duration") or 0)
        formatted_duration = format_seconds(duration_sec, include_hours=(duration_sec >= 3600))

        # Collect available languages
        languages: List[Dict[str, Any]] = []
        seen_codes = set()

        # Manual subtitles
        subs = info.get("subtitles") or {}
        for code, entries in subs.items():
            name = entries[0].get("name", code) if entries else code
            if code not in seen_codes:
                languages.append({
                    "code": code,
                    "name": name,
                    "is_generated": False,
                    "type": "Käsitsi lisatud",
                })
                seen_codes.add(code)

        # Automatic captions
        auto_subs = info.get("automatic_captions") or {}
        for code, entries in auto_subs.items():
            name = entries[0].get("name", code) if entries else code
            if code not in seen_codes:
                languages.append({
                    "code": code,
                    "name": name,
                    "is_generated": True,
                    "type": "Automaatselt loodud",
                })
                seen_codes.add(code)

        # Upload date format YYYY-MM-DD
        raw_date = str(info.get("upload_date") or "")
        upload_date = (
            f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
            if len(raw_date) == 8
            else raw_date
        )

        return VideoMetadata(
            video_id=video_id,
            url=standard_url,
            title=info.get("title") or f"YouTube Video ({video_id})",
            channel=info.get("uploader") or info.get("channel") or "Teadmata kanal",
            channel_url=info.get("uploader_url") or info.get("channel_url") or "",
            duration_seconds=duration_sec,
            duration_formatted=formatted_duration,
            view_count=info.get("view_count") or 0,
            like_count=info.get("like_count") or 0,
            thumbnail=info.get("thumbnail") or f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
            description=info.get("description") or "",
            upload_date=upload_date,
            tags=(info.get("tags") or [])[:15],
            available_languages=languages,
        )

    def transcribe(
        self,
        url: str,
        language: Optional[str] = None,
        timestamps_mode: str = "interval",  # 'none', 'interval', 'sentence'
        interval_seconds: int = 30,
        use_native_markitdown: bool = False,
        fallback_to_audio: bool = True,
    ) -> TranscriptionResult:
        """
        Transcribes a YouTube video into clean Markdown, Plain Text, and SRT.
        
        Args:
            url: YouTube URL or video ID.
            language: Preferred language code ('et', 'en', etc.) or None for auto.
            timestamps_mode: 'interval' (group into N seconds), 'sentence' (every subtitle line),
                             or 'none' (pure paragraphs).
            interval_seconds: Number of seconds per timestamp group in 'interval' mode.
            use_native_markitdown: If True, uses the standard MarkItDown().convert() method.
            fallback_to_audio: If captions are missing, downloads audio and runs speech recognition.
        """
        video_id = extract_video_id(url)
        if not video_id:
            raise ValueError(f"Vigane YouTube URL või video ID: '{url}'")

        standard_url = f"https://www.youtube.com/watch?v={video_id}"
        meta = self.get_video_info(standard_url)

        # Mode A: Native MarkItDown
        if use_native_markitdown:
            return self._transcribe_with_native_markitdown(standard_url, meta, language)

        # Mode B: Enhanced timedtext transcription via yt-dlp download
        try:
            segments, chosen_lang = self._fetch_timedtext_segments(standard_url, meta, language)
            used_engine = "enhanced_timedtext"
        except Exception as e:
            err_msg = str(e)
            if "Sign in to confirm you’re not a bot" in err_msg or "confirm you're not a bot" in err_msg.lower():
                logger.error(f"YouTube nõuab botikontrolli: {err_msg}")
                raise RuntimeError(
                    "YouTube blokeerib selle serveri (VPS) IP-aadressi robotikaitsega ('Sign in to confirm you're not a bot'). "
                    "Lahendus: Lisa serverisse 'cookies.txt' fail (ekspordi oma brauserist YouTube küpsised) "
                    "või kasuta kohalikku masinat (localhost)."
                ) from e

            logger.warning(f"Subtiitrite laadimine ebaõnnestus: {e}")
            if fallback_to_audio and FFMPEG_EXE:
                logger.info("Üritatakse audiotranskriptsiooni (Speech Recognition)...")
                try:
                    segments, chosen_lang = self._transcribe_audio_stream(standard_url, meta, language)
                    used_engine = "audio_fallback"
                except Exception as audio_err:
                    audio_err_msg = str(audio_err)
                    if "Sign in to confirm you’re not a bot" in audio_err_msg or "confirm you're not a bot" in audio_err_msg.lower():
                        raise RuntimeError(
                            "YouTube blokeerib selle serveri (VPS) IP-aadressi robotikaitsega ('Sign in to confirm you're not a bot'). "
                            "Lahendus: Lisa serverisse 'cookies.txt' fail (ekspordi brauserist) või seadista YOUTUBE_COOKIES_FILE."
                        ) from audio_err
                    raise
            else:
                raise RuntimeError(
                    f"Subtiitreid ei leitud videole {video_id}. Täpne viga: {e}"
                ) from e

        # Build output formats
        markdown = self._generate_markdown(meta, segments, timestamps_mode, interval_seconds, chosen_lang)
        plain_text = self._generate_plain_text(segments, timestamps_mode, interval_seconds)
        srt_content = self._generate_srt(segments)

        # Word count & reading time stats
        total_words = len(plain_text.split())
        total_chars = len(plain_text)
        reading_time = max(1, math.ceil(total_words / 200)) if total_words > 0 else 0

        return TranscriptionResult(
            metadata=meta,
            markdown=markdown,
            plain_text=plain_text,
            srt=srt_content,
            segments=segments,
            language=chosen_lang,
            word_count=total_words,
            char_count=total_chars,
            reading_time_minutes=reading_time,
            used_engine=used_engine,
        )

    def _fetch_timedtext_segments(
        self, url: str, meta: VideoMetadata, language: Optional[str] = None
    ) -> Tuple[List[TranscriptSegment], str]:
        """Fetch transcript snippets with start & duration timestamps using yt-dlp."""
        # Find which language to request from available languages
        available_codes = [l["code"] for l in meta.available_languages]
        chosen_lang = "en"

        if language:
            if language in available_codes:
                chosen_lang = language
            else:
                # Find matching prefix (e.g., 'en' for 'en-US')
                matched = [c for c in available_codes if c.startswith(language)]
                if matched:
                    chosen_lang = matched[0]
                elif available_codes:
                    chosen_lang = available_codes[0]
        else:
            # Prefer English or first available
            matched_en = [c for c in available_codes if c.startswith("en")]
            if matched_en:
                chosen_lang = matched_en[0]
            elif available_codes:
                chosen_lang = available_codes[0]

        tmp_dir = tempfile.mkdtemp(prefix="ytsub_")
        try:
            ydl_opts = get_yt_dlp_common_opts()
            ydl_opts.update({
                "skip_download": True,
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": [chosen_lang],
                "subtitlesformat": "vtt/srt/best",
                "outtmpl": os.path.join(tmp_dir, "%(id)s.%(ext)s"),
                "ignoreerrors": True,
            })

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            downloaded_files = os.listdir(tmp_dir)
            vtt_files = [f for f in downloaded_files if f.endswith(".vtt")]
            srt_files = [f for f in downloaded_files if f.endswith(".srt")]

            if vtt_files:
                target_file = os.path.join(tmp_dir, vtt_files[0])
                parts = vtt_files[0].split(".")
                if len(parts) >= 3:
                    chosen_lang = parts[-2]
                with open(target_file, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                segments = self._parse_vtt(content)
                if segments:
                    return segments, chosen_lang

            if srt_files:
                target_file = os.path.join(tmp_dir, srt_files[0])
                parts = srt_files[0].split(".")
                if len(parts) >= 3:
                    chosen_lang = parts[-2]
                with open(target_file, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                segments = self._parse_srt_content(content)
                if segments:
                    return segments, chosen_lang

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        # Fallback to youtube_transcript_api directly
        return self._fetch_via_youtube_transcript_api(meta.video_id, language or chosen_lang)

    def _fetch_via_youtube_transcript_api(
        self, video_id: str, language: Optional[str]
    ) -> Tuple[List[TranscriptSegment], str]:
        """Secondary fallback using youtube-transcript-api with proxy and cookiejar support."""
        import http.cookiejar
        import requests
        from youtube_transcript_api import YouTubeTranscriptApi

        session = requests.Session()
        proxy = os.environ.get("YOUTUBE_PROXY") or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
        if proxy:
            session.proxies = {"http": proxy, "https": proxy}

        cookie_file = find_valid_cookie_file()
        if cookie_file:
            try:
                jar = http.cookiejar.MozillaCookieJar(cookie_file)
                jar.load(ignore_discard=True, ignore_expires=True)
                session.cookies = jar
                logger.info(f"youtube-transcript-api kasutab küpsiseid: {cookie_file}")
            except Exception as e:
                logger.warning(f"Küpsiste laadimine youtube-transcript-api jaoks ebaõnnestus: {e}")

        ytt = YouTubeTranscriptApi(http_client=session)
        transcript_list = ytt.list(video_id)

        target_transcript = None
        chosen_lang = language or "en"

        if language:
            try:
                target_transcript = transcript_list.find_transcript([language])
                chosen_lang = language
            except Exception:
                pass

        if not target_transcript:
            for t in transcript_list:
                target_transcript = t
                chosen_lang = t.language_code
                break

        if not target_transcript:
            raise RuntimeError(f"Ühtegi subtiitrit ei leitud videole {video_id}")

        data = target_transcript.fetch()
        segments = [
            TranscriptSegment(
                start=float(item.start),
                duration=float(item.duration),
                text=re.sub(r"\s+", " ", item.text).strip(),
            )
            for item in data
            if item.text and item.text.strip()
        ]
        return segments, chosen_lang

    def _parse_vtt(self, vtt_text: str) -> List[TranscriptSegment]:
        """Parse WebVTT content extracting timing and text."""
        segments: List[TranscriptSegment] = []
        blocks = vtt_text.split("\n\n")

        time_pattern = re.compile(
            r"((?:(\d{2}):)?(\d{2}):(\d{2})\.(\d{3}))\s+-->\s+((?:(\d{2}):)?(\d{2}):(\d{2})\.(\d{3}))"
        )

        def to_seconds(h_str, m_str, s_str, ms_str) -> float:
            h = int(h_str) if h_str else 0
            m = int(m_str)
            s = int(s_str)
            ms = int(ms_str)
            return h * 3600 + m * 60 + s + (ms / 1000.0)

        for block in blocks:
            lines = [line.strip() for line in block.split("\n") if line.strip()]
            if not lines:
                continue

            time_line_idx = -1
            match = None
            for idx, line in enumerate(lines):
                m = time_pattern.search(line)
                if m:
                    match = m
                    time_line_idx = idx
                    break

            if match and time_line_idx != -1:
                start_sec = to_seconds(match.group(2), match.group(3), match.group(4), match.group(5))
                end_sec = to_seconds(match.group(7), match.group(8), match.group(9), match.group(10))
                duration = max(0.1, end_sec - start_sec)
                text_lines = lines[time_line_idx + 1 :]
                raw_text = " ".join(text_lines)
                clean_text = re.sub(r"<[^>]+>", "", raw_text).strip()
                clean_text = re.sub(r"\s+", " ", clean_text)
                if clean_text:
                    segments.append(TranscriptSegment(start=start_sec, duration=duration, text=clean_text))

        # Deduplicate consecutive identical segments
        deduped: List[TranscriptSegment] = []
        for s in segments:
            if not deduped or deduped[-1].text != s.text:
                deduped.append(s)
        return deduped

    def _parse_srt_content(self, srt_text: str) -> List[TranscriptSegment]:
        """Parse SRT content into TranscriptSegment objects."""
        segments: List[TranscriptSegment] = []
        blocks = re.split(r"\n\s*\n", srt_text.strip())

        time_pattern = re.compile(
            r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s+-->\s+(\d{2}):(\d{2}):(\d{2}),(\d{3})"
        )

        def to_seconds(h, m, s, ms) -> float:
            return int(h) * 3600 + int(m) * 60 + int(s) + (int(ms) / 1000.0)

        for b in blocks:
            lines = [line.strip() for line in b.split("\n") if line.strip()]
            if len(lines) < 2:
                continue

            time_match = None
            text_lines = []
            for line in lines:
                if not time_match:
                    m = time_pattern.search(line)
                    if m:
                        time_match = m
                        continue
                else:
                    text_lines.append(line)

            if time_match and text_lines:
                start_sec = to_seconds(*time_match.groups()[:4])
                end_sec = to_seconds(*time_match.groups()[4:])
                clean_text = " ".join(text_lines).strip()
                if clean_text:
                    segments.append(
                        TranscriptSegment(
                            start=start_sec,
                            duration=max(0.1, end_sec - start_sec),
                            text=clean_text,
                        )
                    )
        return segments

    def _transcribe_audio_stream(
        self, url: str, meta: VideoMetadata, language: Optional[str] = None
    ) -> Tuple[List[TranscriptSegment], str]:
        """
        Audio fallback using FFmpeg + SpeechRecognition on the downloaded audio track.
        """
        import speech_recognition as sr

        logger.info(f"Laadin alla video heliriba transkribeerimiseks: {url}")
        tmp_dir = tempfile.mkdtemp(prefix="ytaudio_")
        try:
            out_path = os.path.join(tmp_dir, "audio.%(ext)s")
            ydl_opts = get_yt_dlp_common_opts()
            ydl_opts.update({
                "format": "bestaudio/best",
                "outtmpl": out_path,
            })
            if FFMPEG_EXE:
                ydl_opts["ffmpeg_location"] = FFMPEG_EXE

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            downloaded_files = os.listdir(tmp_dir)
            if not downloaded_files:
                raise RuntimeError("Heliriba allalaadimine ebaõnnestus.")

            audio_file = os.path.join(tmp_dir, downloaded_files[0])
            wav_path = os.path.join(tmp_dir, "converted.wav")
            logger.info(f"Konverteerin heli WAV formaati: {audio_file}")

            # Direct ffmpeg conversion to 16kHz mono WAV (no ffprobe required)
            cmd = [
                FFMPEG_EXE or "ffmpeg",
                "-y",
                "-i", audio_file,
                "-vn",
                "-acodec", "pcm_s16le",
                "-ar", "16000",
                "-ac", "1",
                wav_path,
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

            recognizer = sr.Recognizer()
            lang_code = language or ("et-EE" if language == "et" else "en-US")

            with sr.AudioFile(wav_path) as source:
                audio_data = recognizer.record(source)
                try:
                    text = recognizer.recognize_google(audio_data, language=lang_code).strip()
                except Exception as ex:
                    logger.warning(f"Google speech viga: {ex}, proovime en-US keelega.")
                    text = recognizer.recognize_google(audio_data, language="en-US").strip()

            if not text:
                text = "[Kõnet ei tuvastatud]"

            segment = TranscriptSegment(start=0.0, duration=float(meta.duration_seconds), text=text)
            return [segment], lang_code
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def _transcribe_with_native_markitdown(
        self, url: str, meta: VideoMetadata, language: Optional[str]
    ) -> TranscriptionResult:
        """Call Microsoft MarkItDown's official convert method."""
        kwargs = {}
        if language:
            kwargs["youtube_transcript_languages"] = [language]

        res = self.md_native.convert(url, **kwargs)
        md_content = res.text_content or ""

        # Extract transcript text
        transcript_match = re.search(r"### Transcript\s*\n+(.*)", md_content, re.DOTALL)
        plain_text = transcript_match.group(1).strip() if transcript_match else md_content.strip()

        words = len(plain_text.split())
        chars = len(plain_text)
        reading_time = max(1, math.ceil(words / 200)) if words > 0 else 0

        segment = TranscriptSegment(start=0.0, duration=float(meta.duration_seconds), text=plain_text)

        return TranscriptionResult(
            metadata=meta,
            markdown=md_content,
            plain_text=plain_text,
            srt=f"1\n00:00:00,000 --> {format_srt_timestamp(float(meta.duration_seconds))}\n{plain_text}\n",
            segments=[segment],
            language=language or "auto",
            word_count=words,
            char_count=chars,
            reading_time_minutes=reading_time,
            used_engine="markitdown_native",
        )

    def _generate_markdown(
        self,
        meta: VideoMetadata,
        segments: List[TranscriptSegment],
        timestamps_mode: str,
        interval_seconds: int,
        language: str,
    ) -> str:
        """Construct a high-quality, structured Markdown document."""
        lines: List[str] = []

        # Title
        lines.append(f"# {meta.title}")
        lines.append("")

        # Visual preview & metadata table
        if meta.thumbnail:
            lines.append(f"[![Vaata YouTube'is]({meta.thumbnail})]({meta.url})")
            lines.append("")

        lines.append("| Parameeter | Väärtus |")
        lines.append("|---|---|")
        lines.append(f"| **Kanal** | [{meta.channel}]({meta.channel_url or meta.url}) |")
        lines.append(f"| **Kestus** | `{meta.duration_formatted}` ({meta.duration_seconds}s) |")
        if meta.view_count:
            lines.append(f"| **Vaatamisi** | {meta.view_count:,} |")
        if meta.upload_date:
            lines.append(f"| **Avaldatud** | {meta.upload_date} |")
        lines.append(f"| **Keel** | `{language}` |")
        lines.append(f"| **Allikas** | [Ava video]({meta.url}) |")
        lines.append("")

        # Tags if available
        if meta.tags:
            tag_badges = " ".join([f"`#{t}`" for t in meta.tags[:8]])
            lines.append(f"**Märksõnad:** {tag_badges}")
            lines.append("")

        # Description (collapsible blockquote)
        if meta.description:
            lines.append("### Video kirjeldus")
            desc_snippet = "\n".join([f"> {line}" for line in meta.description.strip().split("\n")[:8]])
            lines.append(desc_snippet)
            lines.append("")

        # Transcript section
        lines.append("---")
        lines.append("## Transkriptsioon")
        lines.append("")

        if not segments:
            lines.append("*Transkriptsiooni tekst puudub.*")
            return "\n".join(lines)

        if timestamps_mode == "none":
            paragraph_sentences: List[str] = []
            for seg in segments:
                paragraph_sentences.append(seg.text)
                if len(paragraph_sentences) >= 4 or seg.text.endswith((".", "!", "?")):
                    lines.append(" ".join(paragraph_sentences))
                    lines.append("")
                    paragraph_sentences = []
            if paragraph_sentences:
                lines.append(" ".join(paragraph_sentences))
                lines.append("")

        elif timestamps_mode == "sentence":
            for seg in segments:
                t_str = format_seconds(seg.start)
                lines.append(f"- **`[{t_str}]`** {seg.text}")
            lines.append("")

        else:
            # Interval mode (group into chunks of N seconds)
            chunks: List[Tuple[float, float, List[str]]] = []
            current_start = 0.0
            current_texts: List[str] = []
            current_end = current_start + interval_seconds

            for seg in segments:
                if seg.start >= current_end and current_texts:
                    chunks.append((current_start, seg.start, current_texts))
                    current_start = seg.start
                    current_end = current_start + interval_seconds
                    current_texts = [seg.text]
                else:
                    current_texts.append(seg.text)

            if current_texts:
                chunks.append((current_start, segments[-1].end, current_texts))

            for start, end, texts in chunks:
                start_label = format_seconds(start)
                end_label = format_seconds(end)
                combined = " ".join(texts)
                lines.append(f"### `[{start_label} - {end_label}]`")
                lines.append(f"{combined}")
                lines.append("")

        lines.append("---")
        lines.append("> 💡 **Nõuanne:** Saate selle transkriptsiooni kopeerida otse tehisintellekti (ChatGPT, Claude, Gemini), et koostada kokkuvõte, tegevuspunktid või õppematerjal.")

        return "\n".join(lines)

    def _generate_plain_text(
        self,
        segments: List[TranscriptSegment],
        timestamps_mode: str,
        interval_seconds: int,
    ) -> str:
        """Construct clean plain text representation."""
        if not segments:
            return ""

        if timestamps_mode == "none":
            return " ".join(seg.text for seg in segments)

        if timestamps_mode == "sentence":
            return "\n".join(f"[{format_seconds(seg.start)}] {seg.text}" for seg in segments)

        # Interval mode
        output: List[str] = []
        current_start = 0.0
        current_texts: List[str] = []
        current_end = current_start + interval_seconds

        for seg in segments:
            if seg.start >= current_end and current_texts:
                output.append(f"[{format_seconds(current_start)}] {' '.join(current_texts)}")
                current_start = seg.start
                current_end = current_start + interval_seconds
                current_texts = [seg.text]
            else:
                current_texts.append(seg.text)

        if current_texts:
            output.append(f"[{format_seconds(current_start)}] {' '.join(current_texts)}")

        return "\n\n".join(output)

    def _generate_srt(self, segments: List[TranscriptSegment]) -> str:
        """Construct standard SubRip (.srt) subtitle file."""
        entries: List[str] = []
        for idx, seg in enumerate(segments, start=1):
            start_str = format_srt_timestamp(seg.start)
            end_str = format_srt_timestamp(seg.end)
            entries.append(f"{idx}\n{start_str} --> {end_str}\n{seg.text}\n")
        return "\n".join(entries)


class EnhancedMarkItDownYouTubeConverter(DocumentConverter):
    """
    Drop-in custom converter that can be plugged directly into Microsoft MarkItDown:
    
    Example:
        from markitdown import MarkItDown
        from transcriber import EnhancedMarkItDownYouTubeConverter
        
        md = MarkItDown()
        md.register_converter(EnhancedMarkItDownYouTubeConverter(), priority=0)
        res = md.convert('https://www.youtube.com/watch?v=...')
    """

    def __init__(self, timestamps_mode: str = "interval", interval_seconds: int = 30):
        self.transcriber = YouTubeTranscriber()
        self.timestamps_mode = timestamps_mode
        self.interval_seconds = interval_seconds

    def accepts(self, file_stream: io.IOBase, stream_info: StreamInfo, **kwargs: Any) -> bool:
        url = stream_info.url or ""
        return extract_video_id(url) is not None

    def convert(
        self, file_stream: io.IOBase, stream_info: StreamInfo, **kwargs: Any
    ) -> DocumentConverterResult:
        url = stream_info.url or ""
        lang = kwargs.get("language") or kwargs.get("youtube_transcript_languages", [None])[0]
        timestamps = kwargs.get("timestamps_mode", self.timestamps_mode)
        interval = kwargs.get("interval_seconds", self.interval_seconds)

        result = self.transcriber.transcribe(
            url,
            language=lang,
            timestamps_mode=timestamps,
            interval_seconds=interval,
        )

        return DocumentConverterResult(
            markdown=result.markdown,
            title=result.metadata.title,
        )
