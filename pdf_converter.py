"""
PDF to Markdown Converter using Microsoft MarkItDown and PyMuPDF
================================================================
Extracts text, structured tables, document metadata, table of contents,
and handles scanned PDFs via OCR fallback.
"""

from __future__ import annotations

import io
import math
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    from markitdown import MarkItDown
except ImportError:
    MarkItDown = None


@dataclass
class PdfMetadata:
    """Document metadata extracted from PDF properties."""
    filename: str = "document.pdf"
    title: str = "Nimetu PDF"
    author: str = "Teadmata autor"
    subject: str = ""
    keywords: str = ""
    creator: str = ""
    producer: str = ""
    creation_date: str = ""
    mod_date: str = ""
    page_count: int = 0
    file_size_bytes: int = 0
    file_size_formatted: str = "0 B"
    toc: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class PdfPageContent:
    """Content extracted from an individual PDF page."""
    page_num: int  # 1-indexed
    text: str
    markdown: str
    tables: List[List[List[str]]] = field(default_factory=list)
    image_count: int = 0
    is_scanned: bool = False


@dataclass
class StructuredDocument:
    """Structured information extracted from PDF document, tables, forms, and metadata."""
    is_document: bool = True
    document_type: str = "PDF Dokument"
    key_values: Dict[str, str] = field(default_factory=dict)
    tables: List[Dict[str, Any]] = field(default_factory=list)
    spatial_lines: List[str] = field(default_factory=list)
    json_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PdfConversionResult:
    """Complete result returned by the PDF converter."""
    metadata: PdfMetadata
    markdown: str
    plain_text: str
    page_count: int
    word_count: int
    char_count: int
    reading_time_minutes: int
    tables_count: int
    used_engine: str
    pages: List[PdfPageContent] = field(default_factory=list)
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


def table_to_markdown(table: List[List[str]]) -> str:
    """Convert a 2D list of cell values into a Markdown table with aligned pipes."""
    if not table:
        return ""

    # Clean cell values
    cleaned_table: List[List[str]] = []
    for row in table:
        cleaned_row = []
        for cell in row:
            if cell is None:
                cleaned_row.append("")
            else:
                text = str(cell).replace("\n", " ").replace("|", "\\|").strip()
                cleaned_row.append(text)
        # Include row if at least one cell has content
        if any(cell for cell in cleaned_row):
            cleaned_table.append(cleaned_row)

    if not cleaned_table:
        return ""

    # Determine maximum columns
    num_cols = max(len(row) for row in cleaned_table)
    # Pad rows to equal length
    normalized: List[List[str]] = []
    for row in cleaned_table:
        if len(row) < num_cols:
            row = row + [""] * (num_cols - len(row))
        normalized.append(row)

    col_widths = [max(3, max(len(row[c]) for row in normalized)) for c in range(num_cols)]

    def fmt_row(cells: List[str]) -> str:
        parts = [f" {cell.ljust(w)} " for cell, w in zip(cells, col_widths)]
        return "|" + "|".join(parts) + "|"

    lines: List[str] = []
    header = normalized[0]
    lines.append(fmt_row(header))
    # Separator
    sep_parts = ["-" * (w + 2) for w in col_widths]
    lines.append("|" + "|".join(sep_parts) + "|")

    for row in normalized[1:]:
        lines.append(fmt_row(row))

    return "\n".join(lines)


class PdfToMarkdownConverter:
    """
    High-performance PDF to Markdown converter.
    Integrates Microsoft MarkItDown, PyMuPDF, table recognition,
    and optional OCR for scanned pages.
    """

    def __init__(self):
        self.md_instance = MarkItDown() if MarkItDown else None

    def convert(
        self,
        file_input: Union[str, bytes, io.BytesIO],
        filename: str = "document.pdf",
        use_native_markitdown: bool = False,
        extract_tables: bool = True,
        ocr_scanned: bool = True,
    ) -> PdfConversionResult:
        """
        Convert a PDF file to clean Markdown.
        
        Args:
            file_input: File path, bytes, or BytesIO buffer
            filename: Name of the file for metadata
            use_native_markitdown: Force standard Microsoft MarkItDown pipeline
            extract_tables: Detect and format tables as Markdown tables
            ocr_scanned: Run OCR if pages have images but no embedded text
        """
        pdf_bytes = self._read_bytes(file_input)
        file_size = len(pdf_bytes)

        if use_native_markitdown and self.md_instance:
            return self._convert_via_native_markitdown(pdf_bytes, filename, file_size)

        if fitz is not None:
            try:
                return self._convert_via_pymupdf(
                    pdf_bytes,
                    filename=filename,
                    file_size=file_size,
                    extract_tables=extract_tables,
                    ocr_scanned=ocr_scanned,
                )
            except Exception:
                # If PyMuPDF fails, try MarkItDown fallback
                if self.md_instance:
                    return self._convert_via_native_markitdown(pdf_bytes, filename, file_size)
                raise

        if self.md_instance:
            return self._convert_via_native_markitdown(pdf_bytes, filename, file_size)

        raise RuntimeError("Kumbagi ei leitud: ei PyMuPDF (fitz) ega MarkItDown teeki.")

    def _read_bytes(self, file_input: Union[str, bytes, io.BytesIO]) -> bytes:
        if isinstance(file_input, bytes):
            return file_input
        if isinstance(file_input, io.BytesIO):
            return file_input.getvalue()
        if isinstance(file_input, str):
            if os.path.isfile(file_input):
                with open(file_input, "rb") as f:
                    return f.read()
            raise FileNotFoundError(f"PDF faili ei leitud: {file_input}")
        raise ValueError(f"Toetamata sisendi tüüp: {type(file_input)}")

    def _convert_via_native_markitdown(
        self, pdf_bytes: bytes, filename: str, file_size: int
    ) -> PdfConversionResult:
        """Convert using Microsoft MarkItDown's built-in PdfConverter."""
        stream = io.BytesIO(pdf_bytes)
        res = self.md_instance.convert_stream(stream, file_extension=".pdf")
        md_text = res.text_content or ""
        plain = re.sub(r"[#*`_~\[\]|]", "", md_text)
        words = len(plain.split())
        chars = len(plain)
        reading_time = max(1, math.ceil(words / 200)) if words > 0 else 0

        # Attempt to read basic metadata
        title = res.title or os.path.splitext(filename)[0]
        meta = PdfMetadata(
            filename=filename,
            title=title,
            file_size_bytes=file_size,
            file_size_formatted=format_file_size(file_size),
        )

        structured_doc = self._analyze_structure(
            meta, [PdfPageContent(page_num=1, text=plain, markdown=md_text)], plain
        )

        return PdfConversionResult(
            metadata=meta,
            markdown=md_text,
            plain_text=plain,
            page_count=1,
            word_count=words,
            char_count=chars,
            reading_time_minutes=reading_time,
            tables_count=len(structured_doc.tables),
            used_engine="markitdown_native",
            pages=[],
            structured_doc=structured_doc,
        )

    def _convert_via_pymupdf(
        self,
        pdf_bytes: bytes,
        filename: str,
        file_size: int,
        extract_tables: bool,
        ocr_scanned: bool,
    ) -> PdfConversionResult:
        """Rich extraction using PyMuPDF (tables, TOC, metadata, OCR fallback)."""
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_pages = len(doc)

        raw_meta = doc.metadata or {}
        title = raw_meta.get("title", "").strip() or os.path.splitext(filename)[0]
        author = raw_meta.get("author", "").strip() or "Teadmata autor"
        subject = raw_meta.get("subject", "").strip()
        keywords = raw_meta.get("keywords", "").strip()
        creator = raw_meta.get("creator", "").strip()
        producer = raw_meta.get("producer", "").strip()
        creation_date = raw_meta.get("creationDate", "").strip()
        mod_date = raw_meta.get("modDate", "").strip()

        # Parse TOC
        raw_toc = doc.get_toc() or []
        toc_items: List[Dict[str, Any]] = []
        for item in raw_toc:
            if len(item) >= 3:
                lvl, item_title, page_num = item[0], item[1], item[2]
                toc_items.append({"level": lvl, "title": item_title, "page": page_num})

        meta = PdfMetadata(
            filename=filename,
            title=title,
            author=author,
            subject=subject,
            keywords=keywords,
            creator=creator,
            producer=producer,
            creation_date=creation_date,
            mod_date=mod_date,
            page_count=total_pages,
            file_size_bytes=file_size,
            file_size_formatted=format_file_size(file_size),
            toc=toc_items,
        )

        pages_content: List[PdfPageContent] = []
        total_tables = 0

        # Lazy OCR engine import if needed for scanned pages
        ocr_engine = None

        for page_idx in range(total_pages):
            page = doc[page_idx]
            page_num = page_idx + 1

            # Extract raw text
            page_text = page.get_text("text").strip()
            images_on_page = len(page.get_images())
            is_scanned = False

            # Check if page is scanned and needs OCR
            if not page_text and images_on_page > 0 and ocr_scanned:
                is_scanned = True
                try:
                    if ocr_engine is None:
                        from image_converter import get_ocr_engine
                        ocr_engine = get_ocr_engine()
                    pix = page.get_pixmap(dpi=150)
                    img_bytes = pix.tobytes("png")
                    ocr_res, _ = ocr_engine(img_bytes)
                    if ocr_res:
                        page_text = "\n".join([line[1] for line in ocr_res if len(line) >= 2])
                except Exception:
                    pass

            # Extract tables if requested
            page_tables: List[List[List[str]]] = []
            if extract_tables and hasattr(page, "find_tables"):
                try:
                    tabs = page.find_tables()
                    for tab in tabs.tables:
                        extracted = tab.extract()
                        if extracted and len(extracted) > 1:
                            page_tables.append(extracted)
                            total_tables += 1
                except Exception:
                    pass

            # Fallback table extraction from aligned text if no vector tables found
            if extract_tables and not page_tables and page_text:
                fallback_tabs = self._extract_text_tables(page_text)
                if fallback_tabs:
                    page_tables.extend(fallback_tabs)
                    total_tables += len(fallback_tabs)

            # Construct page markdown
            md_lines: List[str] = []
            if page_tables:
                # Add tables
                for t in page_tables:
                    md_lines.append(table_to_markdown(t))
                    md_lines.append("")

            # Add plain text lines
            if page_text:
                md_lines.append(page_text)

            page_md = "\n\n".join(md_lines).strip()

            pages_content.append(
                PdfPageContent(
                    page_num=page_num,
                    text=page_text,
                    markdown=page_md,
                    tables=page_tables,
                    image_count=images_on_page,
                    is_scanned=is_scanned,
                )
            )

        doc.close()

        plain_combined = "\n\n".join([p.text for p in pages_content if p.text])
        structured_doc = self._analyze_structure(meta, pages_content, plain_combined)

        # Build complete document Markdown
        full_markdown = self._generate_full_markdown(meta, pages_content, structured_doc)

        words = len(plain_combined.split())
        chars = len(plain_combined)
        reading_time = max(1, math.ceil(words / 200)) if words > 0 else 0

        return PdfConversionResult(
            metadata=meta,
            markdown=full_markdown,
            plain_text=plain_combined,
            page_count=total_pages,
            word_count=words,
            char_count=chars,
            reading_time_minutes=reading_time,
            tables_count=total_tables,
            used_engine="pymupdf_enhanced",
            pages=pages_content,
            structured_doc=structured_doc,
        )

    def _extract_text_tables(self, text: str) -> List[List[List[str]]]:
        """Fallback table extraction from aligned whitespace or pipe-separated lines."""
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        detected_tables: List[List[List[str]]] = []
        current_table: List[List[str]] = []

        for line in lines:
            parts = re.split(r"\s{2,}|\t|\|", line)
            parts = [p.strip() for p in parts if p.strip()]
            if len(parts) >= 3:
                if not current_table or len(parts) == len(current_table[0]):
                    current_table.append(parts)
                else:
                    if len(current_table) >= 2:
                        detected_tables.append(current_table)
                    current_table = [parts]
            else:
                if len(current_table) >= 2:
                    detected_tables.append(current_table)
                current_table = []

        if len(current_table) >= 2:
            detected_tables.append(current_table)

        return detected_tables

    def _analyze_structure(
        self,
        meta: PdfMetadata,
        pages: List[PdfPageContent],
        plain_text: str,
    ) -> StructuredDocument:
        """Extract structured tables, key-values, 2D layout and JSON schema from PDF."""
        # 1. Collect all tables
        structured_tables: List[Dict[str, Any]] = []
        for p in pages:
            for t in p.tables:
                if len(t) >= 2:
                    headers = [str(c or "").strip() for c in t[0]]
                    rows = [[str(c or "").strip() for c in r] for r in t[1:]]
                    rows = [r for r in rows if any(r)]
                    if any(headers) and rows:
                        structured_tables.append({
                            "page": p.page_num,
                            "headers": headers,
                            "rows": rows,
                        })

        # 2. Extract key-values
        key_values: Dict[str, str] = {}
        if meta.title and meta.title not in ["Nimetu PDF", "dokument.pdf"] and not meta.title.endswith(".pdf"):
            key_values["Dokumendi pealkiri"] = meta.title
        if meta.author and meta.author not in ["Teadmata autor", "Unknown"]:
            key_values["Autor"] = meta.author
        if meta.subject:
            key_values["Teema"] = meta.subject
        if meta.creation_date:
            clean_date = meta.creation_date.replace("D:", "").split("+")[0]
            if len(clean_date) >= 8:
                key_values["Loodud"] = f"{clean_date[:4]}-{clean_date[4:6]}-{clean_date[6:8]}"
        key_values["Lehekülgi"] = str(meta.page_count)
        key_values["Faili maht"] = meta.file_size_formatted

        # Semantic regex rules for document text
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

        raw_lines = [l.strip() for l in plain_text.splitlines() if l.strip()]
        for label, pat, val_pat in rules:
            for i, line in enumerate(raw_lines):
                m = re.match(pat, line, re.IGNORECASE)
                if m:
                    val = m.group(1).strip() if (m.groups() and m.group(1)) else ""
                    if not val and i + 1 < len(raw_lines):
                        cand = raw_lines[i + 1]
                        if re.search(val_pat, cand, re.IGNORECASE):
                            val = cand.strip()
                    if val and label not in key_values:
                        key_values[label] = val
                        break

        # Company / Issuer detection
        company = None
        address = None
        for line in raw_lines:
            if re.search(r"\b(?:OÜ|OU|AS|MTÜ|TÜ|UÜ|Ltd|LLC|Inc|GmbH)\b|\(\d{7,8}\)", line, re.IGNORECASE):
                if not company and len(line) < 60:
                    company = line
            elif re.search(r"\b\d{5}\b|,\s*\d{5}\b|tee\b|tn\b|mnt\b|linn\b|maakond\b|vald\b", line, re.IGNORECASE):
                if not address and len(line) > 5 and not any(v in line for v in key_values.values()):
                    address = line

        if company:
            key_values["Ettevõte / Isik"] = company
        if address:
            key_values["Aadress"] = address

        # Any explicit "Key: Value" lines
        for line in raw_lines:
            if ":" in line and not line.startswith("http"):
                k, v = line.split(":", 1)
                k_clean = k.strip()
                v_clean = v.strip()
                if 2 < len(k_clean) < 30 and v_clean and k_clean not in key_values:
                    if not any(k_clean.lower() == existing.lower() for existing in key_values):
                        key_values[k_clean] = v_clean

        # 3. Document classification
        raw_lower = plain_text.lower()
        has_invoice_indicators = any(k in key_values for k in ["Arve number", "Viitenumber", "Maksetähtaeg", "Viivis"])
        if has_invoice_indicators or "arve" in raw_lower or "invoice" in raw_lower:
            doc_type = "Arve / Maksekviitung (PDF)"
        elif structured_tables and meta.page_count > 1:
            doc_type = "Mitmeleheküljeline tabelaruanne (PDF)"
        elif structured_tables:
            doc_type = "Tabeldokument / Raport (PDF)"
        elif meta.toc:
            doc_type = "Struktureeritud aruanne / Raamat (PDF)"
        else:
            doc_type = "PDF Dokument"

        # 4. Spatial Lines representation
        spatial_lines: List[str] = []
        for t in structured_tables:
            spatial_lines.append(f"--- [Lehekülg {t.get('page', 1)} Tabel] ---")
            spatial_lines.append("    |    ".join(t.get("headers", [])))
            for row in t.get("rows", []):
                spatial_lines.append("    |    ".join(row))
            spatial_lines.append("")

        # 5. Clean JSON Data
        json_data: Dict[str, Any] = {
            "is_document": True,
            "document_type": doc_type,
            "metadata": {
                "filename": meta.filename,
                "title": meta.title,
                "author": meta.author,
                "subject": meta.subject,
                "creator": meta.creator,
                "producer": meta.producer,
                "creation_date": meta.creation_date,
                "page_count": meta.page_count,
                "file_size": meta.file_size_formatted,
                "toc": meta.toc,
            },
            "fields": key_values,
            "tables": structured_tables,
            "pages": [
                {
                    "page_num": p.page_num,
                    "tables_count": len(p.tables),
                    "image_count": p.image_count,
                    "is_scanned": p.is_scanned,
                    "text": p.text,
                }
                for p in pages
            ],
            "spatial_lines": spatial_lines,
            "raw_text": plain_text,
        }

        return StructuredDocument(
            is_document=True,
            document_type=doc_type,
            key_values=key_values,
            tables=structured_tables,
            spatial_lines=spatial_lines,
            json_data=json_data,
        )

    def _generate_full_markdown(
        self,
        meta: PdfMetadata,
        pages: List[PdfPageContent],
        structured_doc: Optional[StructuredDocument] = None,
    ) -> str:
        """Format complete document into clean GitHub-flavored Markdown."""
        lines: List[str] = []

        # Document Header
        lines.append(f"# {meta.title}")
        lines.append("")

        # Metadata Table
        lines.append("| Parameeter | Väärtus |")
        lines.append("|---|---|")
        lines.append(f"| **Failinimi** | `{meta.filename}` |")
        lines.append(f"| **Lehekülgi** | `{meta.page_count}` |")
        lines.append(f"| **Faili maht** | `{meta.file_size_formatted}` |")
        if meta.author and meta.author != "Teadmata autor":
            lines.append(f"| **Autor** | {meta.author} |")
        if meta.subject:
            lines.append(f"| **Teema** | {meta.subject} |")
        if meta.creator:
            lines.append(f"| **Looja/Tarkvara** | `{meta.creator}` |")
        if meta.creation_date:
            clean_date = meta.creation_date.replace("D:", "").split("+")[0]
            if len(clean_date) >= 8:
                formatted_d = f"{clean_date[:4]}-{clean_date[4:6]}-{clean_date[6:8]}"
                lines.append(f"| **Loodud** | {formatted_d} |")
        lines.append("")

        # Table of Contents if available
        if meta.toc:
            lines.append("## Sisukord")
            lines.append("")
            for item in meta.toc:
                indent = "  " * (max(1, item["level"]) - 1)
                lines.append(f"{indent}- **{item['title']}** *(lk {item['page']})*")
            lines.append("")
            lines.append("---")
            lines.append("")

        # Structured Document Section (Key-Values and Form Fields)
        if structured_doc and structured_doc.key_values:
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
        if structured_doc and structured_doc.tables:
            for t_idx, tbl in enumerate(structured_doc.tables, start=1):
                headers = tbl.get("headers", [])
                rows = tbl.get("rows", [])
                page_info = f" (Lk {tbl.get('page', 1)})" if meta.page_count > 1 else ""
                if headers and rows:
                    lines.append(f"### 📦 Tuvastatud tabel #{t_idx}{page_info}")
                    lines.append("")
                    lines.append("| " + " | ".join(headers) + " |")
                    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
                    for row in rows:
                        clean_row = [str(c).replace("|", "\\|") for c in row]
                        lines.append("| " + " | ".join(clean_row) + " |")
                    lines.append("")

        # Page Contents
        for p in pages:
            if meta.page_count > 1:
                lines.append(f"## Lehekülg {p.page_num}")
                lines.append("")

            if p.is_scanned:
                lines.append("> 🔍 *See lehekülg tuvastati OCR abil (skannitud leht ilma digitaalse tekstita).*")
                lines.append("")

            if p.markdown:
                lines.append(p.markdown)
            else:
                lines.append("*[Lehekülg on tühi]*")

            lines.append("")

        return "\n".join(lines).strip()

