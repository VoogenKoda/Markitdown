"""
Unit tests for Microsoft MarkItDown Studio (YouTube, PDF & Images)
"""

import io
import unittest
from fastapi.testclient import TestClient
from markitdown import MarkItDown
from PIL import Image, ImageDraw, ExifTags

from app import app
from image_converter import (
    ImageToMarkdownConverter,
    calculate_aspect_ratio,
    dms_to_degrees,
    format_dms,
)
from pdf_converter import PdfToMarkdownConverter, table_to_markdown
from transcriber import (
    EnhancedMarkItDownYouTubeConverter,
    TranscriptSegment,
    YouTubeTranscriber,
    extract_video_id,
    format_seconds,
    format_srt_timestamp,
    parse_time_str,
)

try:
    import fitz
except ImportError:
    fitz = None


class TestYouTubeTranscriber(unittest.TestCase):
    def test_extract_video_id_standard(self):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        self.assertEqual(extract_video_id(url), "dQw4w9WgXcQ")

    def test_extract_video_id_short(self):
        url = "https://youtu.be/dQw4w9WgXcQ"
        self.assertEqual(extract_video_id(url), "dQw4w9WgXcQ")

    def test_extract_video_id_shorts(self):
        url = "https://www.youtube.com/shorts/dQw4w9WgXcQ"
        self.assertEqual(extract_video_id(url), "dQw4w9WgXcQ")

    def test_extract_video_id_embed(self):
        url = "https://www.youtube.com/embed/dQw4w9WgXcQ"
        self.assertEqual(extract_video_id(url), "dQw4w9WgXcQ")

    def test_extract_video_id_raw(self):
        url = "dQw4w9WgXcQ"
        self.assertEqual(extract_video_id(url), "dQw4w9WgXcQ")

    def test_format_seconds(self):
        self.assertEqual(format_seconds(45), "00:45")
        self.assertEqual(format_seconds(75), "01:15")
        self.assertEqual(format_seconds(3665), "01:01:05")

    def test_parse_time_str(self):
        self.assertEqual(parse_time_str("00:45"), 45.0)
        self.assertEqual(parse_time_str("01:15"), 75.0)
        self.assertEqual(parse_time_str("1:15"), 75.0)
        self.assertEqual(parse_time_str("01:01:05"), 3665.0)
        self.assertEqual(parse_time_str(90), 90.0)
        self.assertEqual(parse_time_str(""), 0.0)
        self.assertEqual(parse_time_str(None), 0.0)

    def test_format_srt_timestamp(self):
        self.assertEqual(format_srt_timestamp(1.5), "00:00:01,500")
        self.assertEqual(format_srt_timestamp(65.123), "00:01:05,123")

    def test_srt_generation(self):
        yt = YouTubeTranscriber()
        segs = [
            TranscriptSegment(start=0.0, duration=2.5, text="Hello world"),
            TranscriptSegment(start=2.5, duration=3.0, text="This is a test"),
        ]
        srt = yt._generate_srt(segs)
        self.assertIn("1\n00:00:00,000 --> 00:00:02,500\nHello world", srt)
        self.assertIn("2\n00:00:02,500 --> 00:00:05,500\nThis is a test", srt)

    def test_markitdown_custom_converter_registration(self):
        md = MarkItDown()
        converter = EnhancedMarkItDownYouTubeConverter()
        md.register_converter(converter, priority=0)
        from markitdown import StreamInfo
        info = StreamInfo(url="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.assertTrue(converter.accepts(None, info))


class TestPdfConverter(unittest.TestCase):
    def test_table_to_markdown(self):
        table_data = [
            ["ID", "Nimi", "Staatus"],
            ["1", "MarkItDown", "Aktiivne"],
            ["2", "RapidOCR", "Valmis"],
        ]
        md_table = table_to_markdown(table_data)
        self.assertIn("| ID", md_table)
        self.assertIn("| Nimi", md_table)
        self.assertTrue(any(line.startswith("|-") for line in md_table.splitlines()))
        self.assertIn("MarkItDown", md_table)

    def test_pdf_conversion(self):
        if fitz is None:
            self.skipTest("PyMuPDF not installed")

        doc = fitz.open()
        doc.set_metadata({
            "title": "Test Document",
            "author": "Antigravity Tester",
        })
        page = doc.new_page()
        page.insert_text((50, 72), "MarkItDown PDF Header", fontsize=16)
        page.insert_text((50, 100), "See on PDF-ist eraldatud testlõik.", fontsize=11)
        pdf_bytes = doc.tobytes()
        doc.close()

        converter = PdfToMarkdownConverter()
        res = converter.convert(pdf_bytes, filename="test.pdf")

        self.assertEqual(res.metadata.filename, "test.pdf")
        self.assertEqual(res.metadata.title, "Test Document")
        self.assertEqual(res.page_count, 1)
        self.assertIn("MarkItDown PDF Header", res.markdown)
        self.assertIn("See on PDF-ist eraldatud testlõik.", res.plain_text)
        self.assertGreater(res.word_count, 0)


class TestImageConverter(unittest.TestCase):
    def test_aspect_ratio(self):
        self.assertEqual(calculate_aspect_ratio(1920, 1080), "16:9")
        self.assertEqual(calculate_aspect_ratio(1080, 1920), "9:16")
        self.assertEqual(calculate_aspect_ratio(1000, 1000), "1:1")

    def test_dms_conversion(self):
        # 59 deg 26 min 14.2 sec N
        dms = ((59, 1), (26, 1), (142, 10))
        deg = dms_to_degrees(dms, "N")
        self.assertAlmostEqual(deg, 59.437278, places=4)
        fmt = format_dms(deg, is_latitude=True)
        self.assertIn("59° 26'", fmt)
        self.assertIn("N", fmt)

    def test_image_ocr(self):
        # Create image with black text on white background
        img = Image.new("RGB", (320, 80), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((20, 30), "MarkItDown OCR", fill=(0, 0, 0))

        buf = io.BytesIO()
        img.save(buf, format="PNG")

        converter = ImageToMarkdownConverter()
        res = converter.convert(buf.getvalue(), filename="test_ocr.png", run_ocr=True)

        self.assertEqual(res.metadata.width, 320)
        self.assertEqual(res.metadata.height, 80)
        self.assertEqual(res.metadata.format, "PNG")
        self.assertIn("Pildi analüüs", res.markdown)
        # Should detect text
        self.assertTrue(len(res.plain_text) > 0)


class TestFastApiEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_endpoint(self):
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("youtube", data["features"])
        self.assertIn("pdf", data["features"])
        self.assertIn("images_exif_ocr", data["features"])

    def test_demo_pdf_endpoint(self):
        resp = self.client.get("/api/demo/pdf")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertIn("markdown", data["data"])
        self.assertIn("plain_text", data["data"])
        self.assertGreater(data["data"]["word_count"], 0)
        self.assertIn("structured", data["data"])
        struct = data["data"]["structured"]
        self.assertTrue(struct["is_document"])
        self.assertIn("tables", struct)
        self.assertIn("json_data", struct)
        self.assertIn("key_values", struct)
        self.assertIn("Dokumendi pealkiri", struct["key_values"])
        self.assertGreater(len(struct["tables"]), 0)

    def test_demo_image_endpoint(self):
        resp = self.client.get("/api/demo/image")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertIn("markdown", data["data"])
        self.assertIn("camera", data["data"]["metadata"])
        self.assertIn("gps", data["data"]["metadata"])
        self.assertTrue(data["data"]["metadata"]["gps"]["has_gps"])

        # Structured document and JSON tests
        self.assertIn("structured", data["data"])
        struct = data["data"]["structured"]
        self.assertTrue(struct["is_document"])
        self.assertIn("Arve", struct["document_type"])
        self.assertIn("key_values", struct)
        self.assertIn("json_data", struct)
        self.assertIn("spatial_lines", struct)
        self.assertGreater(len(struct["key_values"]), 0)
        self.assertIn("Arve number", struct["key_values"])


if __name__ == "__main__":
    unittest.main()
