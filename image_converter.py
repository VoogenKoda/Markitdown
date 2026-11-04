"""
Image to Markdown Converter with EXIF Metadata, OCR and Document Structuring
=============================================================================
Extracts complete EXIF metadata (camera specs, GPS coordinates, shot settings),
performs Optical Character Recognition (OCR) via RapidOCR / pytesseract,
reconstructs 2D spatial layout (columns and rows), and extracts structured
document data (invoices, receipts, forms, key-value pairs and tables).
"""

from __future__ import annotations

import io
import math
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

from PIL import ExifTags, Image

# Global OCR engine singleton
_RAPID_OCR_INSTANCE = None


def get_ocr_engine():
    """Lazy initialize RapidOCR engine."""
    global _RAPID_OCR_INSTANCE
    if _RAPID_OCR_INSTANCE is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            _RAPID_OCR_INSTANCE = RapidOCR()
        except ImportError:
            _RAPID_OCR_INSTANCE = None
    return _RAPID_OCR_INSTANCE


@dataclass
class GpsData:
    """GPS Location metadata extracted from EXIF."""
    has_gps: bool = False
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude_meters: Optional[float] = None
    latitude_dms: str = ""
    longitude_dms: str = ""
    google_maps_url: str = ""


@dataclass
class CameraSpecs:
    """Camera and lens metadata from EXIF."""
    make: str = ""
    model: str = ""
    lens_model: str = ""
    software: str = ""
    exposure_time: str = ""
    f_number: str = ""
    iso: str = ""
    focal_length: str = ""
    focal_length_35mm: str = ""
    flash: str = ""
    datetime_original: str = ""
    metering_mode: str = ""
    white_balance: str = ""
    exposure_program: str = ""


@dataclass
class ImageMetadata:
    """Complete image technical and EXIF metadata."""
    filename: str = "image.jpg"
    format: str = "JPEG"
    mode: str = "RGB"
    width: int = 0
    height: int = 0
    megapixels: float = 0.0
    aspect_ratio: str = ""
    file_size_bytes: int = 0
    file_size_formatted: str = "0 B"
    camera: CameraSpecs = field(default_factory=CameraSpecs)
    gps: GpsData = field(default_factory=GpsData)
    raw_exif: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OcrBlock:
    """Detected text block with coordinates and confidence."""
    text: str
    confidence: float
    box: List[List[float]] = field(default_factory=list)


@dataclass
class StructuredDocument:
    """Structured information extracted from document / invoice / form OCR."""
    is_document: bool = False
    document_type: str = "Tekst"
    key_values: Dict[str, str] = field(default_factory=dict)
    tables: List[Dict[str, Any]] = field(default_factory=list)
    spatial_lines: List[str] = field(default_factory=list)
    json_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ImageConversionResult:
    """Complete result returned by the Image converter."""
    metadata: ImageMetadata
    markdown: str
    plain_text: str
    ocr_blocks: List[OcrBlock] = field(default_factory=list)
    word_count: int = 0
    char_count: int = 0
    ocr_engine: str = "none"
    has_text: bool = False
    structured_doc: StructuredDocument = field(default_factory=StructuredDocument)


def format_file_size(size_bytes: int) -> str:
    """Format bytes into readable string (KB, MB, GB)."""
    if size_bytes <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {units[i]}"


def calculate_aspect_ratio(w: int, h: int) -> str:
    """Calculate standard aspect ratio (e.g., 16:9, 4:3, 1:1)."""
    if w <= 0 or h <= 0:
        return "1:1"
    gcd = math.gcd(w, h)
    rw = w // gcd
    rh = h // gcd
    ratio = w / h
    if abs(ratio - 16 / 9) < 0.05:
        return "16:9"
    if abs(ratio - 9 / 16) < 0.05:
        return "9:16"
    if abs(ratio - 4 / 3) < 0.05:
        return "4:3"
    if abs(ratio - 3 / 2) < 0.05:
        return "3:2"
    if abs(ratio - 1.0) < 0.01:
        return "1:1"
    if rw < 50 and rh < 50:
        return f"{rw}:{rh}"
    return f"{ratio:.2f}:1"


def rational_to_float(val: Any) -> float:
    """Safely convert Pillow IFDRational or tuple to float."""
    if val is None:
        return 0.0
    if hasattr(val, "numerator") and hasattr(val, "denominator"):
        return float(val.numerator) / float(val.denominator) if val.denominator != 0 else 0.0
    if isinstance(val, (tuple, list)) and len(val) == 2:
        return float(val[0]) / float(val[1]) if val[1] != 0 else 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def dms_to_degrees(dms: Any, ref: str) -> Optional[float]:
    """Convert EXIF DMS (Degrees, Minutes, Seconds) to decimal degrees."""
    if not dms or len(dms) < 3:
        return None
    d = rational_to_float(dms[0])
    m = rational_to_float(dms[1])
    s = rational_to_float(dms[2])
    deg = d + (m / 60.0) + (s / 3600.0)
    if ref in ["S", "W", "s", "w"]:
        deg = -deg
    return round(deg, 6)


def format_dms(degrees: float, is_latitude: bool) -> str:
    """Format decimal degrees into DMS string (e.g. 59° 26' 14.2\" N)."""
    if degrees is None:
        return ""
    abs_d = abs(degrees)
    d = int(abs_d)
    rem = (abs_d - d) * 60
    m = int(rem)
    s = (rem - m) * 60
    direction = ""
    if is_latitude:
        direction = "N" if degrees >= 0 else "S"
    else:
        direction = "E" if degrees >= 0 else "W"
    return f"{d}° {m}' {s:.2f}\" {direction}"


class ImageToMarkdownConverter:
    """
    Image to Markdown Converter with Document Structuring.
    Extracts complete EXIF metadata (camera specs, GPS, timestamps),
    performs Optical Character Recognition (OCR), reconstructs 2D layout,
    and extracts structured invoice/document fields and tables.
    """

    def __init__(self):
        self.ocr_engine = get_ocr_engine()

    def convert(
        self,
        image_input: Union[str, bytes, io.BytesIO],
        filename: str = "image.jpg",
        run_ocr: bool = True,
        extract_exif: bool = True,
    ) -> ImageConversionResult:
        """
        Convert an image into Markdown with EXIF metadata, OCR text, and structured data.
        """
        img_bytes = self._read_bytes(image_input)
        file_size = len(img_bytes)

        # Open image with Pillow
        pil_img = Image.open(io.BytesIO(img_bytes))
        width, height = pil_img.size
        img_format = pil_img.format or "JPEG"
        img_mode = pil_img.mode

        megapixels = round((width * height) / 1_000_000, 2)
        aspect = calculate_aspect_ratio(width, height)

        # Extract EXIF
        camera_specs = CameraSpecs()
        gps_data = GpsData()
        raw_exif_dict: Dict[str, Any] = {}

        if extract_exif:
            camera_specs, gps_data, raw_exif_dict = self._extract_exif(pil_img)

        meta = ImageMetadata(
            filename=filename,
            format=img_format,
            mode=img_mode,
            width=width,
            height=height,
            megapixels=megapixels,
            aspect_ratio=aspect,
            file_size_bytes=file_size,
            file_size_formatted=format_file_size(file_size),
            camera=camera_specs,
            gps=gps_data,
            raw_exif=raw_exif_dict,
        )

        # Run OCR
        ocr_blocks: List[OcrBlock] = []
        ocr_engine_name = "none"
        plain_ocr_text = ""

        if run_ocr:
            ocr_blocks, ocr_engine_name, plain_ocr_text = self._run_ocr(img_bytes, pil_img)

        # Reconstruct 2D spatial layout and extract structured document data
        structured_doc = self._analyze_structure(ocr_blocks, plain_ocr_text)

        words = len(plain_ocr_text.split())
        chars = len(plain_ocr_text)

        markdown = self._generate_markdown(
            meta, ocr_blocks, plain_ocr_text, ocr_engine_name, structured_doc
        )

        return ImageConversionResult(
            metadata=meta,
            markdown=markdown,
            plain_text=plain_ocr_text,
            ocr_blocks=ocr_blocks,
            word_count=words,
            char_count=chars,
            ocr_engine=ocr_engine_name,
            has_text=len(plain_ocr_text.strip()) > 0,
            structured_doc=structured_doc,
        )

    def _read_bytes(self, image_input: Union[str, bytes, io.BytesIO]) -> bytes:
        if isinstance(image_input, bytes):
            return image_input
        if isinstance(image_input, io.BytesIO):
            return image_input.getvalue()
        if isinstance(image_input, str):
            if os.path.isfile(image_input):
                with open(image_input, "rb") as f:
                    return f.read()
            raise FileNotFoundError(f"Pildifaili ei leitud: {image_input}")
        raise ValueError(f"Toetamata pildisisendi tüüp: {type(image_input)}")

    def _extract_exif(self, img: Image.Image) -> Tuple[CameraSpecs, GpsData, Dict[str, Any]]:
        """Extract camera specifications and GPS coordinates from image EXIF."""
        camera = CameraSpecs()
        gps = GpsData()
        raw_dict: Dict[str, Any] = {}

        try:
            exif = img.getexif()
            if not exif:
                return camera, gps, raw_dict

            for tag_id, val in exif.items():
                tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                if isinstance(val, bytes):
                    try:
                        val = val.decode("utf-8", errors="ignore").strip("\x00")
                    except Exception:
                        val = str(val)
                raw_dict[tag_name] = str(val)

            camera.make = str(raw_dict.get("Make", "")).strip()
            camera.model = str(raw_dict.get("Model", "")).strip()
            camera.software = str(raw_dict.get("Software", "")).strip()

            try:
                exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
                for tag_id, val in exif_ifd.items():
                    tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                    if isinstance(val, bytes):
                        try:
                            val = val.decode("utf-8", errors="ignore").strip("\x00")
                        except Exception:
                            val = str(val)
                    raw_dict[tag_name] = str(val)

                    if tag_name == "LensModel":
                        camera.lens_model = str(val).strip()
                    elif tag_name == "DateTimeOriginal":
                        camera.datetime_original = str(val).strip()
                    elif tag_name == "ExposureTime":
                        f_exp = rational_to_float(val)
                        if f_exp > 0:
                            if f_exp < 1.0:
                                inv = round(1.0 / f_exp)
                                camera.exposure_time = f"1/{inv}s"
                            else:
                                camera.exposure_time = f"{f_exp:.1f}s"
                    elif tag_name == "FNumber":
                        fn = rational_to_float(val)
                        if fn > 0:
                            camera.f_number = f"f/{fn:.1f}"
                    elif tag_name in ["ISOSpeedRatings", "PhotographicSensitivity"]:
                        camera.iso = f"ISO {val}"
                    elif tag_name == "FocalLength":
                        fl = rational_to_float(val)
                        if fl > 0:
                            camera.focal_length = f"{fl:.1f}mm"
                    elif tag_name == "FocalLengthIn35mmFilm":
                        camera.focal_length_35mm = f"{val}mm (35mm ekv)"
                    elif tag_name == "Flash":
                        camera.flash = "Töötas (Fired)" if val in [1, 5, 7, 9, 13, 15, 25, 29, 31] else "Ei töötanud"
            except Exception:
                pass

            try:
                gps_ifd = exif.get_ifd(ExifTags.IFD.GPSInfo)
                gps_tags: Dict[str, Any] = {}
                for tag_id, val in gps_ifd.items():
                    tag_name = ExifTags.GPSTAGS.get(tag_id, str(tag_id))
                    gps_tags[tag_name] = val

                lat_dms = gps_tags.get("GPSLatitude")
                lat_ref = gps_tags.get("GPSLatitudeRef", "N")
                lon_dms = gps_tags.get("GPSLongitude")
                lon_ref = gps_tags.get("GPSLongitudeRef", "E")

                if lat_dms and lon_dms:
                    lat_dec = dms_to_degrees(lat_dms, lat_ref)
                    lon_dec = dms_to_degrees(lon_dms, lon_ref)

                    if lat_dec is not None and lon_dec is not None:
                        gps.has_gps = True
                        gps.latitude = lat_dec
                        gps.longitude = lon_dec
                        gps.latitude_dms = format_dms(lat_dec, is_latitude=True)
                        gps.longitude_dms = format_dms(lon_dec, is_latitude=False)
                        gps.google_maps_url = f"https://www.google.com/maps?q={lat_dec},{lon_dec}"

                        alt = gps_tags.get("GPSAltitude")
                        if alt is not None:
                            gps.altitude_meters = round(rational_to_float(alt), 1)
            except Exception:
                pass

        except Exception:
            pass

        return camera, gps, raw_dict

    def _run_ocr(
        self, img_bytes: bytes, pil_img: Image.Image
    ) -> Tuple[List[OcrBlock], str, str]:
        """Run OCR on image bytes, returning blocks, engine name, and combined text."""
        blocks: List[OcrBlock] = []

        # 1. Try RapidOCR
        engine = self.ocr_engine or get_ocr_engine()
        if engine is not None:
            try:
                ocr_res, _ = engine(img_bytes)
                if ocr_res:
                    lines: List[str] = []
                    for item in ocr_res:
                        if len(item) >= 2:
                            box = item[0]
                            text = str(item[1]).strip()
                            conf = float(item[2]) if len(item) > 2 else 1.0
                            if text:
                                blocks.append(OcrBlock(text=text, confidence=round(conf, 3), box=box))
                                lines.append(text)
                    combined = "\n".join(lines)
                    return blocks, "rapidocr", combined
            except Exception:
                pass

        # 2. Fallback to pytesseract if installed
        try:
            import pytesseract
            text = pytesseract.image_to_string(pil_img).strip()
            if text:
                for line in text.splitlines():
                    clean = line.strip()
                    if clean:
                        blocks.append(OcrBlock(text=clean, confidence=1.0))
                return blocks, "pytesseract", text
        except Exception:
            pass

        return [], "none", ""

    def _analyze_structure(
        self, ocr_blocks: List[OcrBlock], plain_ocr_text: str
    ) -> StructuredDocument:
        """
        Reconstruct 2D visual layout (rows and columns) and extract
        semantic key-value pairs, tables, and document metadata.
        """
        if not plain_ocr_text.strip() and not ocr_blocks:
            return StructuredDocument()

        # 1. Spatial 2D Line Reconstruction
        spatial_lines = self._reconstruct_spatial_lines(ocr_blocks, plain_ocr_text)

        # 2. Key-Value and Document Field Extraction
        key_values, doc_type, is_doc = self._extract_key_values(spatial_lines, plain_ocr_text)

        # 3. Table Detection
        tables = self._extract_tables(spatial_lines, plain_ocr_text)

        # 4. JSON Representation
        json_data: Dict[str, Any] = {
            "is_document": is_doc,
            "document_type": doc_type,
            "fields": key_values,
            "tables": tables,
            "spatial_text": "\n".join(spatial_lines),
            "raw_text": plain_ocr_text,
        }

        return StructuredDocument(
            is_document=is_doc,
            document_type=doc_type,
            key_values=key_values,
            tables=tables,
            spatial_lines=spatial_lines,
            json_data=json_data,
        )

    def _reconstruct_spatial_lines(
        self, ocr_blocks: List[OcrBlock], plain_ocr_text: str
    ) -> List[str]:
        """
        Group OCR blocks by vertical coordinates into true 2D horizontal lines,
        preserving column alignments and visual reading order.
        """
        valid_blocks = [b for b in ocr_blocks if b.box and len(b.box) >= 4 and b.text.strip()]
        if not valid_blocks:
            return [l.strip() for l in plain_ocr_text.splitlines() if l.strip()]

        class BBox:
            def __init__(self, block: OcrBlock):
                self.text = block.text.strip()
                xs = [p[0] for p in block.box]
                ys = [p[1] for p in block.box]
                self.xmin = min(xs)
                self.xmax = max(xs)
                self.ymin = min(ys)
                self.ymax = max(ys)
                self.height = max(1.0, self.ymax - self.ymin)
                self.center_y = (self.ymin + self.ymax) / 2.0
                self.center_x = (self.xmin + self.xmax) / 2.0

        items = [BBox(b) for b in valid_blocks]
        items.sort(key=lambda b: (b.ymin, b.xmin))

        # Cluster into lines based on vertical overlap
        lines: List[List[BBox]] = []
        for item in items:
            placed = False
            for line in lines:
                l_ymin = min(b.ymin for b in line)
                l_ymax = max(b.ymax for b in line)
                l_h = max(1.0, l_ymax - l_ymin)
                l_cy = sum(b.center_y for b in line) / len(line)
                overlap = max(0.0, min(item.ymax, l_ymax) - max(item.ymin, l_ymin))

                if (overlap > 0.35 * min(item.height, l_h)) or (abs(item.center_y - l_cy) < max(8.0, 0.40 * l_h)):
                    line.append(item)
                    placed = True
                    break
            if not placed:
                lines.append([item])

        # Sort lines top-to-bottom
        lines.sort(key=lambda l: min(b.ymin for b in l))

        # Format items within each line left-to-right
        reconstructed: List[str] = []
        for line in lines:
            line.sort(key=lambda b: b.xmin)
            line_parts: List[str] = []
            for idx, box in enumerate(line):
                if idx == 0:
                    line_parts.append(box.text)
                else:
                    prev = line[idx - 1]
                    gap = box.xmin - prev.xmax
                    # If gap is small, join as regular words in same block
                    if gap < max(20.0, 1.25 * box.height):
                        line_parts.append(" " + box.text)
                    else:
                        # Clear visual column gap
                        line_parts.append("    |    " + box.text)
            reconstructed.append("".join(line_parts).strip())

        return reconstructed

    def _extract_key_values(
        self, spatial_lines: List[str], raw_text: str
    ) -> Tuple[Dict[str, str], str, bool]:
        """
        Extract document key-value pairs (invoices, receipts, forms)
        using spatial lines and raw text heuristics.
        """
        raw_lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
        all_lines = spatial_lines if spatial_lines else raw_lines

        key_values: Dict[str, str] = {}

        # Semantic rules for invoices and business documents
        rules = [
            ("Arve number", r"^\s*(?:arve\s*(?:nr|number|no)?|invoice\s*(?:no|number)?)\s*[:.]?\s*(\S+)?$", r"^[A-Z0-9-]{3,25}$"),
            ("Viitenumber", r"^\s*(?:viitenumber|vitenumber|ref(?:erence)?(?:\s*nr)?)\s*[:.]?\s*(\S+)?$", r"^\d{4,16}$"),
            ("Kuupäev", r"^\s*(?:kuup[aä]ev|date|datum)\s*[:.]?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})?$", r"^\d{1,2}[./-]\d{1,2}[./-]\d{2,4}$"),
            ("Maksetähtaeg", r"^\s*(?:makset[aä]htaeg|t[aä]htaeg|due\s*date)\s*[:.]?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})?$", r"^\d{1,2}[./-]\d{1,2}[./-]\d{2,4}$"),
            ("Viivis", r"^\s*(?:viivis|vivis)\s*[:.]?\s*(.+)?$", r"^[0-9.,]+%"),
            ("Selgitus", r"^\s*(?:selgitus)\s*[:.]?\s*(.+)?$", r".+"),
            ("Kogusumma", r"^\s*(?:kokku\s*(?:tasuda)?|maksmisele\s*kuulub|summa\s*kokku|total(?:\s*due)?|summa)\s*[:.]?\s*([0-9\s.,]+(?:\s*(?:EUR|eur|€|\$|USD))?)?$", r"^[0-9\s.,]+(?:\s*(?:EUR|eur|€|\$|USD))?$"),
            ("Pangakonto / IBAN", r"^\s*(?:IBAN|konto|a/a)\s*[:.]?\s*([A-Z]{2}\d{2}[A-Z0-9\s]{12,30})?$", r"^[A-Z]{2}\d{2}[A-Z0-9\s]{12,30}$"),
        ]

        for label, pat, val_pat in rules:
            # 1. Search in spatial lines (often contain 'Key: Value' together)
            found = False
            for line in all_lines:
                # Remove column bars if checking parts
                segments = line.split("|")
                for seg in segments:
                    seg = seg.strip()
                    m = re.match(pat, seg, re.IGNORECASE)
                    if m:
                        val = m.group(1).strip() if (m.groups() and m.group(1)) else ""
                        if val:
                            key_values[label] = val
                            found = True
                            break
                if found:
                    break

            # 2. Search in raw sequential lines (Key on one line, Value on following line)
            if not found:
                for i, line in enumerate(raw_lines):
                    m = re.match(pat, line, re.IGNORECASE)
                    if m:
                        val = m.group(1).strip() if (m.groups() and m.group(1)) else ""
                        if not val:
                            # Immediate next line if it doesn't end with a colon
                            if i + 1 < len(raw_lines) and not raw_lines[i + 1].endswith(":"):
                                cand = raw_lines[i + 1]
                                if re.search(val_pat, cand, re.IGNORECASE):
                                    val = cand.strip()
                            if not val:
                                for j in range(i + 1, min(i + 4, len(raw_lines))):
                                    cand = raw_lines[j]
                                    if cand.endswith(":"):
                                        continue
                                    if re.search(val_pat, cand, re.IGNORECASE):
                                        val = cand.strip()
                                        break
                        if val:
                            key_values[label] = val
                            break

        # 3. Detect Company / Issuer and Address
        company = None
        address = None
        for line in raw_lines:
            # Match company indicators (OÜ, AS, MTÜ, Ltd, GmbH, reg code)
            if re.search(r"\b(?:OÜ|OU|AS|MTÜ|TÜ|UÜ|Ltd|LLC|Inc|GmbH)\b|\(\d{7,8}\)", line, re.IGNORECASE):
                if not company and len(line) < 60:
                    company = line
            # Match street / postal address (e.g., 5-digit postal code, tee, tn, mnt, Treimani)
            elif re.search(r"\b\d{5}\b|,\s*\d{5}\b|tee\b|tn\b|mnt\b|linn\b|maakond\b|vald\b", line, re.IGNORECASE):
                if not address and len(line) > 5 and not any(v in line for v in key_values.values()):
                    address = line

        if company:
            key_values["Ettevõte / Isik"] = company
        if address:
            key_values["Aadress"] = address

        # 4. Check for any generic "Key: Value" lines not yet captured
        for line in all_lines:
            for part in line.split("|"):
                part = part.strip()
                if ":" in part and not part.startswith("http"):
                    k, v = part.split(":", 1)
                    k_clean = k.strip()
                    v_clean = v.strip()
                    if 2 < len(k_clean) < 30 and v_clean and k_clean not in key_values:
                        if not any(k_clean.lower() in existing.lower() for existing in key_values):
                            key_values[k_clean] = v_clean

        # Determine document type
        has_invoice_indicators = any(k in key_values for k in ["Arve number", "Viitenumber", "Maksetähtaeg", "Viivis"])
        raw_lower = raw_text.lower()
        if has_invoice_indicators or "arve" in raw_lower or "invoice" in raw_lower:
            doc_type = "Arve / Maksekviitung"
            is_doc = True
        elif "tšekk" in raw_lower or "receipt" in raw_lower or "kassa" in raw_lower:
            doc_type = "Kassatšekk / Kviitung"
            is_doc = True
        elif "tellimus" in raw_lower or "order" in raw_lower or "pakkumus" in raw_lower:
            doc_type = "Tellimus / Hinnapakkumine"
            is_doc = True
        elif len(key_values) >= 2:
            doc_type = "Struktureeritud vorm / Dokument"
            is_doc = True
        else:
            doc_type = "Tekstidokument"
            is_doc = False

        return key_values, doc_type, is_doc

    def _extract_tables(
        self, spatial_lines: List[str], raw_text: str
    ) -> List[Dict[str, Any]]:
        """Detect and structure tabular regions from OCR output."""
        tables: List[Dict[str, Any]] = []
        raw_lines = [l.strip() for l in raw_text.splitlines() if l.strip()]

        table_keywords = {
            "kirjeldus", "kogus", "periood", "teenus", "summa", "hind", "km",
            "toode", "ühik", "description", "qty", "period", "service",
            "amount", "total", "price", "unit"
        }

        # 1. Check if spatial lines contain multi-column table headers (with '|')
        for line_idx, line in enumerate(spatial_lines):
            parts = [p.strip() for p in line.split("|") if p.strip()]
            matching_kw = [p for p in parts if p.lower() in table_keywords or any(kw in p.lower() for kw in table_keywords)]
            if len(parts) >= 3 and len(matching_kw) >= 2:
                # Found table header row in spatial lines
                headers = parts
                rows = []
                for sub_line in spatial_lines[line_idx + 1:]:
                    sub_parts = [p.strip() for p in sub_line.split("|") if p.strip()]
                    if not sub_parts or len(sub_parts) < 2:
                        break
                    # Normalize columns
                    if len(sub_parts) < len(headers):
                        sub_parts += [""] * (len(headers) - len(sub_parts))
                    rows.append(sub_parts[:len(headers)])
                if rows:
                    tables.append({"headers": headers, "rows": rows})
                    return tables

        # 2. Check for consecutive table headers in sequential lines
        seq_headers = []
        seq_start = -1
        for i, line in enumerate(raw_lines):
            clean = line.strip().lower()
            if clean in table_keywords:
                if not seq_headers:
                    seq_start = i
                seq_headers.append(line.strip())
            else:
                if len(seq_headers) >= 3:
                    break
                elif seq_headers:
                    seq_headers = []
                    seq_start = -1

        if len(seq_headers) >= 3 and seq_start != -1:
            data_lines = []
            for j in range(seq_start + len(seq_headers), len(raw_lines)):
                l = raw_lines[j]
                if any(kw in l.lower() for kw in ["kokku", "maksekorraldusel", "total", "iban"]):
                    break
                data_lines.append(l)

            if data_lines:
                num_cols = len(seq_headers)
                rows = []
                # Distribute data lines into rows
                for k in range(0, len(data_lines), num_cols):
                    chunk = data_lines[k:k + num_cols]
                    if len(chunk) < num_cols:
                        chunk += [""] * (num_cols - len(chunk))
                    rows.append(chunk)
                tables.append({"headers": seq_headers, "rows": rows})

        return tables

    def _generate_markdown(
        self,
        meta: ImageMetadata,
        ocr_blocks: List[OcrBlock],
        plain_text: str,
        ocr_engine: str,
        structured_doc: StructuredDocument,
    ) -> str:
        """Construct rich Markdown representation for an image."""
        lines: List[str] = []

        lines.append(f"# 🖼️ Pildi analüüs: {meta.filename}")
        lines.append("")

        # Technical Parameters Table
        lines.append("### Tehnilised andmed")
        lines.append("| Parameeter | Väärtus |")
        lines.append("|---|---|")
        lines.append(f"| **Failinimi** | `{meta.filename}` |")
        lines.append(f"| **Mõõtmed** | `{meta.width} × {meta.height}` px |")
        lines.append(f"| **Eraldusvõime** | `{meta.megapixels} MP` |")
        lines.append(f"| **Kuvasuhe** | `{meta.aspect_ratio}` |")
        lines.append(f"| **Formaat** | `{meta.format}` ({meta.mode}) |")
        lines.append(f"| **Faili maht** | `{meta.file_size_formatted}` |")
        lines.append("")

        # Camera & EXIF specs
        cam = meta.camera
        has_camera_info = any([cam.make, cam.model, cam.lens_model, cam.f_number, cam.exposure_time, cam.iso])
        if has_camera_info:
            lines.append("### 📷 Kaamera & EXIF sätted")
            lines.append("| Seadistus | Väärtus |")
            lines.append("|---|---|")
            if cam.make or cam.model:
                lines.append(f"| **Kaamera** | {cam.make} {cam.model} |")
            if cam.lens_model:
                lines.append(f"| **Objektiiv** | {cam.lens_model} |")
            if cam.datetime_original:
                lines.append(f"| **Pildistatud** | `{cam.datetime_original}` |")
            if cam.exposure_time:
                lines.append(f"| **Säriaeg** | `{cam.exposure_time}` |")
            if cam.f_number:
                lines.append(f"| **Ava (F-stop)** | `{cam.f_number}` |")
            if cam.iso:
                lines.append(f"| **Tundlikkus** | `{cam.iso}` |")
            if cam.focal_length:
                fl_str = cam.focal_length
                if cam.focal_length_35mm:
                    fl_str += f" ({cam.focal_length_35mm})"
                lines.append(f"| **Fookuskaugus** | `{fl_str}` |")
            if cam.flash:
                lines.append(f"| **Välk** | {cam.flash} |")
            if cam.software:
                lines.append(f"| **Tarkvara** | `{cam.software}` |")
            lines.append("")

        # GPS Location
        if meta.gps.has_gps:
            gps = meta.gps
            lines.append("### 📍 Asukoha koordinaadid (GPS)")
            lines.append("| Parameeter | Väärtus |")
            lines.append("|---|---|")
            lines.append(f"| **Laiuskraad (Lat)** | `{gps.latitude}°` ({gps.latitude_dms}) |")
            lines.append(f"| **Pikkuskraad (Lon)** | `{gps.longitude}°` ({gps.longitude_dms}) |")
            if gps.altitude_meters is not None:
                lines.append(f"| **Kõrgus merepinnast** | `{gps.altitude_meters} m` |")
            lines.append(f"| **Kaart** | [Ava Google Mapsis]({gps.google_maps_url}) |")
            lines.append("")
            lines.append(f"> 🗺️ **[Vaata pildistamise asukohta Google Maps kaardil]({gps.google_maps_url})**")
            lines.append("")

        # Structured Document Section (Invoices, Receipts, Forms)
        if structured_doc.is_document or structured_doc.key_values:
            lines.append("---")
            lines.append("## 📋 Struktureeritud dokumendi andmed")
            lines.append("")
            lines.append("| Andmeväli | Tuvastatud väärtus |")
            lines.append("|---|---|")
            lines.append(f"| **Dokumendi tüüp** | **{structured_doc.document_type}** |")
            for k, v in structured_doc.key_values.items():
                lines.append(f"| **{k}** | `{v}` |")
            lines.append("")

        # Structured Tables Section
        if structured_doc.tables:
            for t_idx, tbl in enumerate(structured_doc.tables, start=1):
                headers = tbl.get("headers", [])
                rows = tbl.get("rows", [])
                if headers and rows:
                    lines.append(f"### 📦 Tuvastatud kaubaread & tabel #{t_idx}")
                    lines.append("")
                    lines.append("| " + " | ".join(headers) + " |")
                    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
                    for row in rows:
                        clean_row = [str(c).replace("|", "\\|") for c in row]
                        lines.append("| " + " | ".join(clean_row) + " |")
                    lines.append("")

        # 2D Spatial Layout Section (Aligned Columns)
        if structured_doc.spatial_lines and len(structured_doc.spatial_lines) > 1:
            lines.append("---")
            lines.append("## 📑 Tuvastatud ruumiline paigutus (2D Layout)")
            lines.append("")
            lines.append("```text")
            for sp_line in structured_doc.spatial_lines:
                lines.append(sp_line)
            lines.append("```")
            lines.append("")

        # Raw OCR Section
        lines.append("---")
        lines.append("## 🔍 Toortekst (Raw OCR)")
        lines.append("")

        if plain_text.strip():
            lines.append(f"> Mootor: `{ocr_engine}` • Tuvastatud sõnu: **{len(plain_text.split())}**")
            lines.append("")
            lines.append(plain_text)
            lines.append("")
        else:
            lines.append("*Pildilt ei tuvastatud ühtegi loetavat tekstiplokki.*")
            lines.append("")

        return "\n".join(lines).strip()
