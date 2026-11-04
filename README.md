# 🚀 MarkItDown Studio (YouTube • PDF • Pildid & OCR)

Võimas ja moodne **multiformaatne Markdown konverter**, mis põhineb [Microsoft MarkItDown](https://github.com/microsoft/markitdown) raamistikul, PyMuPDF-il ja RapidOCR süvaõppemudelil.

Muuda suvaline **YouTube video**, **PDF dokument (koos tabelitega)** või **Pildifail (koos täielike EXIF andmete, GPS-i ja tekstituvastusega)** puhtaks, AI-valmis Markdowniks ühe sekundiga.

---

## ✨ Peamised võimalused

### 1. 🎬 YouTube Kõnetranskribeerija & Konspekteerija
- **Täpsed ajatemplid**:
  - **Intervall**: Grupeerib laused valitud ajavahemiku kaupa (nt 30s plokkidena).
  - **Lause kaupa**: Kuvab iga lause/subtiitri oma ajatempliga.
  - **Puhas tekst**: Ajatempliteta sidus tekst.
- **Mitme keele tugi**: Tuvastab autori lisatud ja automaatsed subtiitrid.
- **Audio Fallback**: Subtiitrite puudumisel teisendatakse helivoog otse kõnetuvastusega (`SpeechRecognition` + `imageio-ffmpeg`).
- **Eksport**: `.md` (Markdown), `.txt`, `.srt` (SubRip subtiitrid) ja `.json`.
- **Hulgitöötlus (Batch Mode)**: Kleebi nimekiri linkidest ja saa kõigi videote konspektid korraga kätte.

### 2. 📄 PDF -> Markdown & Tabelite Tuvastus
- **Tabelite ekstraheerimine**: Tuvastab keerukad tabelid ja genereerib veatu Markdown tabelivormingu (`|---|---|`).
- **Täielikud metaandmed**: Eraldab pealkirja, autori, teema, looja tarkvara, lehekülgede arvu, faili mahu ja loomiskuupäeva.
- **Sisukorra tugi (Bookmarks / TOC)**: Kuvab PDF-i hierarhilise sisukorra koos leheküljenumbritega.
- **Skannitud lehtede OCR fallback**: Kui leht on skannitud pilt ilma digitaalse tekstita, tuvastatakse tekst automaatselt optilise OCR mootoriga.
- **Mootorid**: PyMuPDF kõrgtasemel paigutusanalüüs või Microsoft MarkItDown algne `pdfplumber` toru.

### 3. 🖼️ Pildid: EXIF Metaandmed & OCR Tekstituvastus
- **Täielikud EXIF kaamera andmed**:
  - Kaamera mark ja mudel (nt *Sony Alpha 7R V*, *Apple iPhone*, *Canon EOS*)
  - Objektiivi mudel ja fookuskaugus (sh 35mm ekvivalendina)
  - Säriaeg (nt `1/250s`), ava (nt `f/2.8`), ISO tundlikkus ja välgu olek
  - Pildistamise originaalne kuupäev ja kellaaeg
- **Täpne GPS asukoht**:
  - Arvutab laius- ja pikkuskraadid nii kraadides/minutites/sekundites kui kümnendkujul
  - Kõrgus merepinnast (meetrites)
  - **Otselink Google Maps kaardile** pildistamise asukoha vahetuks avamiseks
- **Optiline tekstituvastus (OCR)**:
  - Kiire ja ülitäpne tekstituvastus tänu `RapidOCR` ONNX tehisnärvivõrgule
  - Toetab eesti, inglise jt keeli, trükiteksti, tabeleid, numbreid ja silte
  - Fallback `pytesseract` toele
- **Tehniline profiil**: Pildi mõõtmed (px), eraldusvõime (megapikslites), kuvasuhe (`16:9`, `4:3`, `1:1`), failivorming ja maht.

### 4. 💡 Sisseehitatud AI Promptid
Ühe klikiga kopeeritavad promptid koos teisendatud sisuga:
- 📋 **Lühike kokkuvõte & 5 põhipunkti**
- 🎯 **Tegevuskava & kronoloogilised ülesanded**
- 💡 **Küsimused & vastused (KKK)**
- 📚 **Õppekonspekt & analüüs**

---

## 📦 Paigaldamine

```bash
pip install -r requirements.txt
```

---

## 🚀 Kasutamine

### 1. Veebirakendus (Web UI)

Käivita server käsuga:

```bash
python app.py
```

Ava veebibrauseris: **[http://localhost:8000](http://localhost:8000)**

Veebiliides pakub:
- **Režiimide vahetajat**: Vali sujuvalt YouTube, PDF või Piltide vahel
- **Drag-and-Drop failide üleslaadimist**: Lohista PDF või pilt otse aknasse
- **Reaalajas pildi eelvaadet ja tehnilisi andmeid**
- **Kiirproovide (Demo) nuppe**: Proovi süsteemi ühe klikiga näidisfailidega
- **Vahetut kopeerimist ja failide allalaadimist (.MD, .TXT, .SRT)**

---

### 2. Käsurealt kasutamine (CLI)

Tööriist tuvastab automaatselt, kas tegemist on YouTube lingi, PDF dokumendi või pildiga:

#### YouTube video transkribeerimine:
```bash
# Markdown konspekt terminalis:
python cli.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Salvesta Markdown faili:
python cli.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ" -o video.md

# Ekspordi SRT subtiitrid:
python cli.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ" -f srt -o subtiitrid.srt

# 60s intervalliga ajatemplid:
python cli.py "https://youtu.be/dQw4w9WgXcQ" -t interval -i 60 -o video.md
```

#### PDF dokumendi teisendamine Markdowniks:
```bash
# Teisenda PDF koos tabelite ja struktuuriga:
python cli.py raport.pdf -o raport.md

# Kuva ainult PDF-i metaandmed ja tabelite info:
python cli.py raport.pdf --info
```

#### Pildi analüüsimine (EXIF metaandmed & OCR tekst):
```bash
# Eralda pildi EXIF, GPS ja OCR tekst:
python cli.py foto.jpg -o foto.md

# Ainult EXIF ja pildi info ilma OCR-ita:
python cli.py foto.jpg --no-ocr

# Ekspordi JSON struktuurina:
python cli.py foto.jpg -f json -o andmed.json
```

---

### 3. Python SDK kasutamine

#### PDF dokumendi teisendamine:
```python
from pdf_converter import PdfToMarkdownConverter

converter = PdfToMarkdownConverter()
result = converter.convert("aruanne.pdf")

print("Pealkiri:", result.metadata.title)
print("Lehekülgi:", result.page_count)
print("Tabelite arv:", result.tables_count)
print(result.markdown)
```

#### Pildi EXIF & OCR analüüs:
```python
from image_converter import ImageToMarkdownConverter

converter = ImageToMarkdownConverter()
result = converter.convert("puhkusefoto.jpg")

# Kaamera ja säritus
print(f"Kaamera: {result.metadata.camera.make} {result.metadata.camera.model}")
print(f"Säritus: {result.metadata.camera.exposure_time}, {result.metadata.camera.f_number}")

# GPS asukoht
if result.metadata.gps.has_gps:
    print(f"Asukoht: {result.metadata.gps.latitude}, {result.metadata.gps.longitude}")
    print(f"Google Maps: {result.metadata.gps.google_maps_url}")

# OCR tuvastatud tekst
print("Tuvastatud tekst:\n", result.plain_text)
```

#### YouTube video transkribeerimine:
```python
from transcriber import YouTubeTranscriber

yt = YouTubeTranscriber()
result = yt.transcribe("https://www.youtube.com/watch?v=dQw4w9WgXcQ", interval_seconds=30)
print(result.markdown)
```

---

## 🌐 Majutamine VPS-is (Docker)

Docker konteiner sisaldab kõiki vajalikke süsteemiteeke (`ffmpeg`, `tesseract-ocr`, `libgl` jne):

### Docker Compose käivitamine:
```bash
docker compose up -d --build
```

Rakendus on saadaval pordil `8085` (või `8000`): `http://<sinu-ip>:8085`

---

## 🤖 n8n ja REST API Integratsioon

Teenusel on täielik REST API koos automaatse Swagger dokumentatsiooniga:
- **Swagger UI:** `https://markitdown.sinudomeen.ee/docs`
- **ReDoc:** `https://markitdown.sinudomeen.ee/redoc`
- **OpenAPI JSON:** `https://markitdown.sinudomeen.ee/openapi.json`

Täpse samm-sammult n8n seadistusjuhendi, väljade kaardistused ja imporditava workflow JSON koodi leiad failist:  
👉 **[N8N_AND_API.md](N8N_AND_API.md)**

---

## 📁 Failide struktuur

```
Markitdown/
├── app.py                   # FastAPI veebiserver ja API lõpp-punktid
├── cli.py                   # Universaalne CLI tööriist (YouTube, PDF, Pildid)
├── pdf_converter.py         # PDF -> Markdown mootor (PyMuPDF, MarkItDown, tabelid, OCR)
├── image_converter.py       # Pildi analüüsi mootor (EXIF, GPS koordinaadid, RapidOCR)
├── transcriber.py           # YouTube kõnetranskribeerimise mootor
├── requirements.txt         # Projekti sõltuvused
├── Dockerfile               # Töövalmis Docker konteineri definitsioon
├── docker-compose.yml       # Ühe käsuga käivituse konfiguratsioon
├── README.md                # Dokumentatsioon
├── static/
│   ├── css/style.css        # Moodne Dark/Glassmorphism kujundus & dropzone stiilid
│   └── js/app.js            # Interaktiivne UI, režiimide vahetus, drag-and-drop
├── templates/
│   └── index.html           # SPA veebilehe mall (Multi-Tool Studio)
└── tests/
    └── test_transcriber.py  # Ühiktestid (YouTube, PDF, Image, API)
```
