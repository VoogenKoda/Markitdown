"""
Command-Line Interface for Microsoft MarkItDown Studio
======================================================
Usage:
    # 1. YouTube Transcriber
    python cli.py "https://www.youtube.com/watch?v=..."
    python cli.py "https://youtu.be/..." -o video.md --timestamps interval -i 30

    # 2. PDF to Markdown
    python cli.py document.pdf -o document.md
    python cli.py document.pdf --info

    # 3. Image Analysis (EXIF & OCR)
    python cli.py photo.jpg -o photo.md
    python cli.py photo.png --no-ocr
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich.table import Table

from image_converter import ImageToMarkdownConverter
from pdf_converter import PdfToMarkdownConverter
from transcriber import YouTubeTranscriber, extract_video_id, format_seconds, parse_time_str

console = Console()

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tiff", ".bmp"}


def display_banner():
    banner_text = (
        "[bold cyan]Microsoft MarkItDown Studio[/bold cyan] [bold white]• CLI[/bold white]\n"
        "[dim]YouTube kõne • PDF dokumendid • Piltide EXIF & OCR Markdowniks[/dim]"
    )
    console.print(Panel(banner_text, border_style="cyan", expand=False))


def display_video_info(transcriber: YouTubeTranscriber, url: str):
    with Progress(
        SpinnerColumn(style="cyan"),
        TextColumn("[bold cyan]Laadin video andmeid...[/bold cyan]"),
        transient=True,
    ) as progress:
        progress.add_task("info", total=None)
        meta = transcriber.get_video_info(url)

    table = Table(title=f"Video Info: {meta.title}", border_style="bright_blue")
    table.add_column("Väli", style="cyan bold", width=20)
    table.add_column("Väärtus", style="white")

    table.add_row("ID", meta.video_id)
    table.add_row("Pealkiri", meta.title)
    table.add_row("Kanal", meta.channel)
    table.add_row("Kestus", f"{meta.duration_formatted} ({meta.duration_seconds}s)")
    table.add_row("Vaatamisi", f"{meta.view_count:,}")
    table.add_row("Avaldatud", meta.upload_date)
    table.add_row("URL", meta.url)

    console.print(table)

    if meta.available_languages:
        lang_table = Table(title="Saadaolevad keeled / subtiitrid", border_style="green")
        lang_table.add_column("Kood", style="yellow bold", width=12)
        lang_table.add_column("Keel", style="white", width=25)
        lang_table.add_column("Tüüp", style="dim")

        for lang in meta.available_languages:
            lang_table.add_row(lang["code"], lang["name"], lang["type"])

        console.print(lang_table)
    else:
        console.print("[yellow]Hoiatus: Subtiitrite nimekirja ei leitud. Vajadusel kasutatakse audiopõhist tuvastust.[/yellow]")


def handle_pdf(source: str, args):
    path = Path(source)
    if not path.is_file():
        console.print(f"[bold red]Viga: PDF faili '{source}' ei leitud![/bold red]")
        sys.exit(1)

    converter = PdfToMarkdownConverter()

    with Progress(
        SpinnerColumn(style="magenta"),
        TextColumn("[bold magenta]Teisendan PDF faili Markdowniks...[/bold magenta]"),
        transient=True,
    ) as progress:
        progress.add_task("pdf", total=None)
        res = converter.convert(
            file_input=str(path),
            filename=path.name,
            use_native_markitdown=args.native,
            extract_tables=not args.no_tables,
            ocr_scanned=not args.no_ocr,
        )

    # Info table
    table = Table(title=f"📄 PDF Dokument: {res.metadata.filename}", border_style="magenta")
    table.add_column("Parameeter", style="magenta bold", width=20)
    table.add_column("Väärtus", style="white")

    table.add_row("Pealkiri", res.metadata.title)
    if res.metadata.author != "Teadmata autor":
        table.add_row("Autor", res.metadata.author)
    table.add_row("Lehekülgi", str(res.page_count))
    table.add_row("Faili maht", res.metadata.file_size_formatted)
    table.add_row("Tabelite arv", str(res.tables_count))
    table.add_row("Sõnade arv", f"{res.word_count:,}")
    table.add_row("Tähemärke", f"{res.char_count:,}")
    table.add_row("Lugemisaeg", f"~{res.reading_time_minutes} min")
    table.add_row("Mootor", res.used_engine)

    console.print(table)

    if args.info:
        return

    output_content = res.markdown
    if args.format == "plain":
        output_content = res.plain_text
    elif args.format == "json":
        output_content = json.dumps({
            "metadata": {
                "filename": res.metadata.filename,
                "title": res.metadata.title,
                "author": res.metadata.author,
                "page_count": res.page_count,
                "file_size": res.metadata.file_size_formatted,
            },
            "word_count": res.word_count,
            "markdown": res.markdown,
            "plain_text": res.plain_text,
        }, indent=2, ensure_ascii=False)

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(output_content, encoding="utf-8")
        console.print(f"\n[bold green]✓ PDF edukalt salvestatud faili: {args.output}[/bold green]\n")
    else:
        console.print("\n[bold]Markdown eelvaade:[/bold]\n")
        syntax = Syntax(res.markdown[:2500], "markdown", theme="monokai", line_numbers=False)
        console.print(syntax)
        if len(res.markdown) > 2500:
            console.print("\n[dim]... (täispika sisu salvestamiseks kasuta -o väljund.md) ...[/dim]\n")


def handle_image(source: str, args):
    path = Path(source)
    if not path.is_file():
        console.print(f"[bold red]Viga: Pildifaili '{source}' ei leitud![/bold red]")
        sys.exit(1)

    converter = ImageToMarkdownConverter()

    with Progress(
        SpinnerColumn(style="yellow"),
        TextColumn("[bold yellow]Analüüsin pildi EXIF andmeid ja käivitan OCR-i...[/bold yellow]"),
        transient=True,
    ) as progress:
        progress.add_task("image", total=None)
        res = converter.convert(
            image_input=str(path),
            filename=path.name,
            run_ocr=not args.no_ocr,
            extract_exif=not args.no_exif,
        )

    # Info table
    table = Table(title=f"🖼️ Pildi analüüs: {res.metadata.filename}", border_style="yellow")
    table.add_column("Parameeter", style="yellow bold", width=22)
    table.add_column("Väärtus", style="white")

    table.add_row("Mõõtmed", f"{res.metadata.width} × {res.metadata.height} px ({res.metadata.aspect_ratio})")
    table.add_row("Eraldusvõime", f"{res.metadata.megapixels} MP")
    table.add_row("Formaat", f"{res.metadata.format} ({res.metadata.mode})")
    table.add_row("Faili maht", res.metadata.file_size_formatted)

    cam = res.metadata.camera
    if cam.make or cam.model:
        table.add_row("Kaamera", f"{cam.make} {cam.model}".strip())
    if cam.lens_model:
        table.add_row("Objektiiv", cam.lens_model)
    if cam.exposure_time or cam.f_number or cam.iso:
        settings_str = f"{cam.exposure_time} | {cam.f_number} | {cam.iso} | {cam.focal_length}".strip(" |")
        table.add_row("Sätted", settings_str)
    if cam.datetime_original:
        table.add_row("Pildistatud", cam.datetime_original)

    gps = res.metadata.gps
    if gps.has_gps:
        table.add_row("GPS koordinaadid", f"{gps.latitude}°, {gps.longitude}°")
        table.add_row("Google Maps", gps.google_maps_url)

    table.add_row("OCR tekstituvastus", f"{res.word_count} sõna (Mootor: {res.ocr_engine})")

    console.print(table)

    if args.info:
        return

    output_content = res.markdown
    if args.format == "plain":
        output_content = res.plain_text
    elif args.format == "json":
        output_content = json.dumps({
            "metadata": {
                "filename": res.metadata.filename,
                "width": res.metadata.width,
                "height": res.metadata.height,
                "megapixels": res.metadata.megapixels,
                "camera": {
                    "make": cam.make,
                    "model": cam.model,
                    "lens": cam.lens_model,
                },
                "gps": {
                    "has_gps": gps.has_gps,
                    "latitude": gps.latitude,
                    "longitude": gps.longitude,
                    "maps_url": gps.google_maps_url,
                },
            },
            "word_count": res.word_count,
            "ocr_text": res.plain_text,
            "markdown": res.markdown,
        }, indent=2, ensure_ascii=False)

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(output_content, encoding="utf-8")
        console.print(f"\n[bold green]✓ Pildi analüüs edukalt salvestatud: {args.output}[/bold green]\n")
    else:
        console.print("\n[bold]Markdown eelvaade:[/bold]\n")
        syntax = Syntax(res.markdown[:2500], "markdown", theme="monokai", line_numbers=False)
        console.print(syntax)


def handle_youtube(url: str, args):
    transcriber = YouTubeTranscriber()

    if args.info:
        display_video_info(transcriber, url)
        return

    with Progress(
        SpinnerColumn(style="cyan"),
        TextColumn("[bold cyan]Transkribeerin YouTube videot...[/bold cyan]"),
        transient=True,
    ) as progress:
        progress.add_task("transcribe", total=None)
        res = transcriber.transcribe(
            url,
            language=args.lang,
            timestamps_mode=args.timestamps,
            interval_seconds=args.interval,
            use_native_markitdown=args.native,
        )

    # Success stats
    table = Table(title="Transkriptsiooni kokkuvõte", border_style="cyan")
    table.add_column("Näitaja", style="cyan bold", width=20)
    table.add_column("Väärtus", style="white")

    table.add_row("Pealkiri", res.metadata.title)
    table.add_row("Kanal", res.metadata.channel)
    table.add_row("Kestus", res.metadata.duration_formatted)
    table.add_row("Sõnade arv", f"{res.word_count:,}")
    table.add_row("Tähemärke", f"{res.char_count:,}")
    table.add_row("Lugemisaeg", f"~{res.reading_time_minutes} min")
    table.add_row("Kasutatud mootor", res.used_engine)
    table.add_row("Keel", res.language)

    console.print(table)

    output_content = ""
    if args.format == "markdown":
        output_content = res.markdown
    elif args.format == "plain":
        output_content = res.plain_text
    elif args.format == "srt":
        output_content = res.srt
    elif args.format == "json":
        data = {
            "metadata": {
                "video_id": res.metadata.video_id,
                "title": res.metadata.title,
                "channel": res.metadata.channel,
                "duration": res.metadata.duration_seconds,
            },
            "language": res.language,
            "word_count": res.word_count,
            "markdown": res.markdown,
            "plain_text": res.plain_text,
            "srt": res.srt,
        }
        output_content = json.dumps(data, indent=2, ensure_ascii=False)

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(output_content, encoding="utf-8")
        console.print(f"\n[bold green]✓ Edukalt salvestatud faili: {args.output}[/bold green]\n")
    else:
        console.print("\n[bold]Eelvaade (Markdown):[/bold]\n")
        syntax = Syntax(res.markdown[:2000], "markdown", theme="monokai", line_numbers=False)
        console.print(syntax)
        if len(res.markdown) > 2000:
            console.print("\n[dim]... (kogu sisu kuvamiseks kasuta -o failinimi.md) ...[/dim]\n")


def main():
    if sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description="Microsoft MarkItDown Studio: YouTube videod, PDF failid ja Piltide EXIF/OCR Markdowniks."
    )
    parser.add_argument("source", nargs="?", help="YouTube video URL/ID, PDF faili tee (.pdf) või pildifaili tee (.jpg, .png jne)")
    parser.add_argument("-o", "--output", help="Väljundfaili teekond (nt tulemus.md)")
    parser.add_argument(
        "-f",
        "--format",
        choices=["markdown", "plain", "srt", "json"],
        default="markdown",
        help="Väljundformaat (vaikimisi: markdown)",
    )
    parser.add_argument(
        "-t",
        "--timestamps",
        choices=["interval", "sentence", "none"],
        default="interval",
        help="YouTube ajatemplite režiim: interval (30s kaupa), sentence (rea haaval), none (ilma)",
    )
    parser.add_argument(
        "-i",
        "--interval",
        type=int,
        default=30,
        help="Intervalli pikkus sekundites 'interval' režiimis (vaikimisi: 30)",
    )
    parser.add_argument("-l", "--lang", help="Keelekood (nt 'et', 'en', 'de')")
    parser.add_argument(
        "--info",
        action="store_true",
        help="Kuva ainult metaandmed",
    )
    parser.add_argument(
        "--native",
        action="store_true",
        help="Kasuta Microsoft MarkItDown algset konverterit",
    )
    parser.add_argument(
        "--no-ocr",
        action="store_true",
        help="Keela tekstituvastus (OCR)",
    )
    parser.add_argument(
        "--no-exif",
        action="store_true",
        help="Keela EXIF metaandmete ekstraheerimine",
    )
    parser.add_argument(
        "--no-tables",
        action="store_true",
        help="Keela PDF tabelite struktuurne tuvastus",
    )
    parser.add_argument(
        "--batch",
        help="Tekstifail URL-ide või failiteedega hulgitöötlemiseks",
    )

    args = parser.parse_args()

    display_banner()

    if args.batch:
        batch_path = Path(args.batch)
        if not batch_path.is_file():
            console.print(f"[red]Viga: Faili '{args.batch}' ei leitud![/red]")
            sys.exit(1)

        lines = [line.strip() for line in batch_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        console.print(f"[bold green]Leiti {len(lines)} kirjet hulgitöötlemiseks.[/bold green]")

        out_dir = Path("transcripts")
        out_dir.mkdir(exist_ok=True)
        transcriber = YouTubeTranscriber()

        for idx, item in enumerate(lines, start=1):
            console.print(f"\n[bold cyan]({idx}/{len(lines)}) Töötlen: {item}[/bold cyan]")
            try:
                res = transcriber.transcribe(
                    item,
                    language=args.lang,
                    timestamps_mode=args.timestamps,
                    interval_seconds=args.interval,
                )
                safe_title = "".join(c for c in res.metadata.title if c.isalnum() or c in (" ", "-", "_")).strip()
                out_file = out_dir / f"{res.metadata.video_id}_{safe_title[:40]}.md"
                out_file.write_text(res.markdown, encoding="utf-8")
                console.print(f"[green]✓ Salvestatud: {out_file} ({res.word_count} sõna)[/green]")
            except Exception as e:
                console.print(f"[red]✗ Viga: {e}[/red]")
        return

    if not args.source:
        parser.print_help()
        sys.exit(1)

    src = args.source.strip()
    ext = Path(src).suffix.lower()

    if ext == ".pdf":
        handle_pdf(src, args)
    elif ext in IMAGE_EXTENSIONS:
        handle_image(src, args)
    else:
        # Defaults to YouTube URL or ID
        handle_youtube(src, args)


if __name__ == "__main__":
    main()
