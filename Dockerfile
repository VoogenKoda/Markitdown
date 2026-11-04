FROM python:3.11-slim

# Paigalda ffmpeg, tesseract-ocr, libgl, nodejs ja tööriistad
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    nodejs \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Paigalda Pythoni sõltuvused
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopeeri rakenduse kood
COPY . .

# Ava port
EXPOSE 8000

# Käivita rakendus
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
