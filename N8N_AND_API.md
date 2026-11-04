# 🤖 n8n ja REST API Integratsiooni Juhend

Käesolev juhend selgitab, kuidas kasutada **Microsoft MarkItDown Studio** teenust REST API kaudu ja integreerida see otse **n8n** automatiseerimise töövoogudesse.

---

## 📑 Sisukord
1. [API Üldinfo & Swagger Dokumentatsioon](#-api-üldinfo--swagger-dokumentatsioon)
2. [Ühenduse valikud n8n-iga](#-ühenduse-valikud-n8n-iga)
3. [Töövoog 1: PDF dokumendid ja arved](#-töövoog-1-pdf-dokumendid-ja-arved)
4. [Töövoog 2: Pildid, kviitungid ja OCR](#-töövoog-2-pildid-kviitungid-ja-ocr)
5. [Töövoog 3: YouTube kõne transkribeerimine](#-töövoog-3-youtube-kõne-transkribeerimine)
6. [Kopeeritav n8n Workflow näidis](#-kopeeritav-n8n-workflow-näidis)

---

## 🌐 API Üldinfo & Swagger Dokumentatsioon

Rakendus põhineb FastAPIL, millel on sisseehitatud OpenAPI tugi ja interaktiivne dokumentatsioon:

* **Interaktiivne Swagger UI:**  
  👉 `https://markitdown.sinudomeen.ee/docs` (või lokaalselt `http://localhost:8085/docs`)
* **ReDoc alternatiivne vaade:**  
  👉 `https://markitdown.sinudomeen.ee/redoc`
* **OpenAPI skeem (JSON):**  
  👉 `https://markitdown.sinudomeen.ee/openapi.json`

---

## 🔌 Ühenduse valikud n8n-iga

Sõltuvalt sellest, kus sinu n8n asub:

1. **Avalik HTTPS aadress (töötab igalt poolt):**
   ```text
   https://markitdown.sinudomeen.ee
   ```
2. **Sisevõrgu aadress (kui n8n ja MarkItDown jooksevad samas VPS-is):**
   ```text
   http://172.17.0.1:8085
   ```
   *(Eelis: eriti kiire, puudub võrguliikluse kulu ja ei sõltu välisest internetiühendusest ega domeenist).*

---

## 📄 Töövoog 1: PDF dokumendid ja arved

Kasuta seda töövoogu nt e-mailiga (IMAP/Gmail) saabunud arvete, lepingute või raportite automaatseks lugemiseks.

### n8n "HTTP Request" Node seadistus:

* **Method:** `POST`
* **URL:** `https://markitdown.sinudomeen.ee/api/convert/pdf`
* **Send Body:** Lülita sisse (`true`)
* **Body Content Type:** `Form-Data (multipart/form-data)`
* **Form-Data Parameters:**

| Parameeter | Tüüp | Väärtus n8n-is | Selgitus |
|---|---|---|---|
| `file` | File | `data` (või sinu binary välja nimi) | PDF faili binaarandmed |
| `extract_tables` | Text | `true` | Tuvastab tabelid ja teisendab need Markdown tabeliteks |
| `ocr_scanned` | Text | `true` | Kui leht on skannitud pilt, käivitab OCR-i |

### Olulised väljundväljad n8n-is:
* `$json.data.markdown` ➔ Puhas Markdown tekst koos tabelite ja pealkirjadega (sobib LLM-i / ChatGPT sisendiks).
* `$json.data.structured.is_document` ➔ `true`/`false`
* `$json.data.structured.document_type` ➔ nt `"Arve / Maksekviitung (PDF)"` või `"Tabelaruanne / Raport (PDF)"`
* `$json.data.structured.key_values` ➔ Eraldatud rekvisiidid:
  * `Arve number`, `Viitenumber`, `Kuupäev`, `Maksetähtaeg`, `Kogusumma`, `IBAN`, `Ettevõte / Isik`, `Aadress`
* `$json.data.structured.tables` ➔ Massiiv tuvastatud tabelitest (headers ja rows):
  ```json
  [
    {
      "page": 1,
      "headers": ["Kirjeldus", "Kogus", "Summa"],
      "rows": [["Domeen", "1 tk", "15.00 EUR"]]
    }
  ]
  ```

---

## 🖼️ Töövoog 2: Pildid, kviitungid ja OCR

Kasuta seda nt Telegrami, WhatsAppi või Google Drive'i kaudu saabunud kviitungite, fotode või dokumentide tuvastamiseks.

### n8n "HTTP Request" Node seadistus:

* **Method:** `POST`
* **URL:** `https://markitdown.sinudomeen.ee/api/convert/image`
* **Send Body:** Lülita sisse (`true`)
* **Body Content Type:** `Form-Data (multipart/form-data)`
* **Form-Data Parameters:**

| Parameeter | Tüüp | Väärtus n8n-is | Selgitus |
|---|---|---|---|
| `file` | File | `data` | Pildifail (JPG, PNG, WEBP, TIFF) |
| `run_ocr` | Text | `true` | Käivitab RapidOCR tekstituvastuse |
| `extract_exif` | Text | `true` | Loeb kaamera ja GPS koordinaadid |

### Olulised väljundväljad n8n-is:
* `$json.data.plain_text` ➔ Kõik pildilt loetud sõnad.
* `$json.data.structured.key_values` ➔ Tuvastatud arve väljad.
* `$json.data.metadata.camera` ➔ Kaamera mudel, säriaeg, fookuskaugus jne.
* `$json.data.metadata.gps` ➔ Laius- ja pikkuskraadid ning Google Mapsi otselink:
  ```json
  {
    "has_gps": true,
    "latitude": 59.4370,
    "longitude": 24.7536,
    "google_maps_url": "https://www.google.com/maps?q=59.437,24.7536"
  }
  ```

---

## 🎬 Töövoog 3: YouTube kõne transkribeerimine

Kasuta seda YouTube videote automaatseks kokkuvõtmiseks ja konspekteerimiseks.

### n8n "HTTP Request" Node seadistus:

* **Method:** `POST`
* **URL:** `https://markitdown.sinudomeen.ee/api/transcribe`
* **Send Body:** Lülita sisse (`true`)
* **Body Content Type:** `JSON`
* **Specify Body:**

```json
{
  "url": "{{ $json.youtube_url }}",
  "language": "et",
  "timestamps_mode": "interval",
  "interval_seconds": 30
}
```

### Olulised väljundväljad n8n-is:
* `$json.data.markdown` ➔ Ajatemplitega struktureeritud konspekt.
* `$json.data.srt` ➔ Valmis `.srt` subtiitrifaili sisu.
* `$json.data.metadata.title` ➔ Video pealkiri.
* `$json.data.metadata.channel` ➔ Kanali nimi.

---

## 📋 Kopeeritav n8n Workflow näidis

Saad kopeerida alloleva koodi ja kleepida otse oma **n8n lõuendile (Ctrl + V)**:

```json
{
  "nodes": [
    {
      "parameters": {
        "method": "POST",
        "url": "https://markitdown.sinudomeen.ee/api/convert/pdf",
        "sendBody": true,
        "contentType": "multipart-form-data",
        "bodyParameters": {
          "parameters": [
            {
              "parameterType": "formBinaryData",
              "name": "file",
              "inputDataFieldName": "data"
            },
            {
              "name": "extract_tables",
              "value": "true"
            },
            {
              "name": "ocr_scanned",
              "value": "true"
            }
          ]
        },
        "options": {
          "timeout": 300000
        }
      },
      "id": "1f8b4a2e-4b71-4603-912a-markitdown01",
      "name": "MarkItDown PDF Konverter",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [460, 300]
    }
  ],
  "connections": {}
}
```

---

## ⚙️ Soovituslikud Nginxi sätted suurte failide jaoks
Kui n8n saadab serverisse suuri PDF faile (nt üle 1 MB), veendu, et Nginx Proxy Manageri **Advanced (⚙️)** vahelehel on kirjas:
```nginx
client_max_body_size 100M;
proxy_read_timeout 300s;
proxy_connect_timeout 300s;
proxy_send_timeout 300s;
```
See hoiab ära `413 Request Entity Too Large` ja `504 Gateway Timeout` vead.

