/**
 * Microsoft MarkItDown Studio
 * Client-Side Application for YouTube, PDF & Images (EXIF + OCR)
 */

document.addEventListener("DOMContentLoaded", () => {
  // State
  let currentMode = "youtube"; // "youtube" | "pdf" | "image"
  let currentResult = null;
  let selectedPdfFile = null;
  let selectedImageFile = null;
  let lastFetchedUrl = null;
  let infoFetchTimeout = null;

  // Mode Elements
  const modeButtons = document.querySelectorAll(".mode-btn");
  const heroTitle = document.getElementById("hero-title");
  const heroDesc = document.getElementById("hero-desc");
  const heroPillText = document.getElementById("hero-pill-text");
  const youtubeSection = document.getElementById("youtube-section");
  const pdfSection = document.getElementById("pdf-section");
  const imageSection = document.getElementById("image-section");

  // YouTube Controls
  const urlInput = document.getElementById("youtube-url-input");
  const pasteBtn = document.getElementById("paste-btn");
  const clearBtn = document.getElementById("clear-btn");
  const transcribeBtn = document.getElementById("transcribe-btn");
  const transcribeBtnText = document.getElementById("transcribe-btn-text");
  const speechChips = document.querySelectorAll("#speech-chips .chip-btn");
  const previewCard = document.getElementById("video-preview-card");
  const previewThumb = document.getElementById("preview-thumb");
  const previewTitle = document.getElementById("preview-title");
  const previewChannel = document.getElementById("preview-channel");
  const previewDuration = document.getElementById("preview-duration");
  const previewViews = document.getElementById("preview-views");
  const previewDate = document.getElementById("preview-date");
  const previewSubsCount = document.getElementById("preview-subs-count");
  const previewYtLink = document.getElementById("preview-yt-link");
  const timestampsModePills = document.querySelectorAll("#timestamps-mode-group .radio-pill");
  const intervalField = document.getElementById("interval-field");
  const intervalSlider = document.getElementById("interval-slider");
  const intervalDisplay = document.getElementById("interval-display");
  const languageSelect = document.getElementById("language-select");
  const langHelper = document.getElementById("lang-helper");
  const nativeToggle = document.getElementById("native-toggle");

  // PDF Controls
  const pdfDropzone = document.getElementById("pdf-dropzone");
  const pdfFileInput = document.getElementById("pdf-file-input");
  const pdfSelectedBox = document.getElementById("pdf-selected-box");
  const pdfFileName = document.getElementById("pdf-file-name");
  const pdfFileSize = document.getElementById("pdf-file-size");
  const pdfRemoveBtn = document.getElementById("pdf-remove-btn");
  const convertPdfBtn = document.getElementById("convert-pdf-btn");
  const convertPdfBtnText = document.getElementById("convert-pdf-btn-text");
  const demoPdfBtn = document.getElementById("demo-pdf-btn");
  const pdfTablesToggle = document.getElementById("pdf-tables-toggle");
  const pdfOcrToggle = document.getElementById("pdf-ocr-toggle");
  const pdfNativeToggle = document.getElementById("pdf-native-toggle");

  // Image Controls
  const imageDropzone = document.getElementById("image-dropzone");
  const imageFileInput = document.getElementById("image-file-input");
  const imageSelectedBox = document.getElementById("image-selected-box");
  const imagePreviewThumb = document.getElementById("image-preview-thumb");
  const imageFileName = document.getElementById("image-file-name");
  const imageDimensionsBadge = document.getElementById("image-dimensions-badge");
  const imageFileSizeBadge = document.getElementById("image-file-size");
  const imageRemoveBtn = document.getElementById("image-remove-btn");
  const convertImageBtn = document.getElementById("convert-image-btn");
  const convertImageBtnText = document.getElementById("convert-image-btn-text");
  const demoImageBtn = document.getElementById("demo-image-btn");
  const imageOcrToggle = document.getElementById("image-ocr-toggle");
  const imageExifToggle = document.getElementById("image-exif-toggle");

  // Loading & Error Elements
  const loadingPanel = document.getElementById("loading-panel");
  const loadingTitle = document.getElementById("loading-step-title");
  const loadingSub = document.getElementById("loading-step-desc");
  const errorBanner = document.getElementById("error-banner");
  const errorMessage = document.getElementById("error-message");
  const errorClose = document.getElementById("error-close");

  // Results Elements
  const resultsCard = document.getElementById("results-card");
  const statVal1 = document.getElementById("stat-val-1");
  const statLbl1 = document.getElementById("stat-lbl-1");
  const statVal2 = document.getElementById("stat-val-2");
  const statLbl2 = document.getElementById("stat-lbl-2");
  const statVal3 = document.getElementById("stat-val-3");
  const statLbl3 = document.getElementById("stat-lbl-3");
  const statVal4 = document.getElementById("stat-val-4");
  const statLbl4 = document.getElementById("stat-lbl-4");

  const resultsTabs = document.querySelectorAll("#results-tabs .tab-btn");
  const tabBtnPlain = document.getElementById("tab-btn-plain");
  const tabBtnSrt = document.getElementById("tab-btn-srt");
  const tabBtnMeta = document.getElementById("tab-btn-meta");
  const tabBtnStructured = document.getElementById("tab-btn-structured");
  const renderedContent = document.getElementById("rendered-content");
  const rawMarkdownCode = document.getElementById("raw-markdown-code");
  const plainTextContent = document.getElementById("plain-text-content");
  const srtCode = document.getElementById("srt-code");
  const metadataViewContainer = document.getElementById("metadata-view-container");
  const structuredViewContainer = document.getElementById("structured-view-container");

  const copyBtn = document.getElementById("copy-btn");
  const downloadJsonBtn = document.getElementById("download-json-btn");
  const downloadMdBtn = document.getElementById("download-md-btn");
  const downloadTxtBtn = document.getElementById("download-txt-btn");
  const downloadSrtBtn = document.getElementById("download-srt-btn");
  const promptCopyBtns = document.querySelectorAll(".prompt-copy-btn");

  // Toast & Batch Elements
  const toast = document.getElementById("toast");
  const toastMessage = document.getElementById("toast-message");
  const batchToggleBtn = document.getElementById("batch-toggle-btn");
  const batchModal = document.getElementById("batch-modal");
  const batchCloseBtn = document.getElementById("batch-close-btn");
  const batchUrlsInput = document.getElementById("batch-urls-input");
  const batchStartBtn = document.getElementById("batch-start-btn");
  const batchResultsList = document.getElementById("batch-results-list");

  // Configure marked.js
  if (window.marked) {
    marked.setOptions({ breaks: true, gfm: true });
  }

  // --- Helper Functions ---
  function showToast(msg, isError = false) {
    toastMessage.textContent = msg;
    toast.className = isError ? "toast show error" : "toast show";
    setTimeout(() => toast.classList.remove("show"), 2800);
  }
  window.showToast = showToast;

  function showError(msg) {
    errorMessage.textContent = msg;
    errorBanner.style.display = "flex";
  }

  function hideError() {
    errorBanner.style.display = "none";
  }

  function formatBytes(bytes) {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  }

  function extractYouTubeId(url) {
    if (!url) return null;
    const trimmed = url.trim();
    const patterns = [
      /(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?\/\s]{11})/i,
      /^[a-zA-Z0-9_-]{11}$/,
    ];
    for (const pattern of patterns) {
      const match = trimmed.match(pattern);
      if (match) return match[1] || match[0];
    }
    return null;
  }

  // =========================================================================
  // 🔄 MODE SWITCHING
  // =========================================================================

  function switchMode(newMode) {
    currentMode = newMode;
    hideError();

    modeButtons.forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.mode === newMode);
    });

    youtubeSection.style.display = newMode === "youtube" ? "block" : "none";
    pdfSection.style.display = newMode === "pdf" ? "block" : "none";
    imageSection.style.display = newMode === "image" ? "block" : "none";

    if (newMode === "youtube") {
      heroTitle.innerHTML = 'Muuda iga YouTube video <span class="gradient-text">puhtaks Markdowniks</span>';
      heroDesc.textContent = "Transkribeeri kõne, eralda ajatemplid, kopeeri konspekt või ekspordi LLM-valmis tekstiks ja subtiitriteks sekunditega.";
      heroPillText.textContent = "Tehisintellekti jaoks optimeeritud Markdown & Subtiitrid";
    } else if (newMode === "pdf") {
      heroTitle.innerHTML = 'Teisenda PDF dokumendid <span class="gradient-text">struktureeritud Markdowniks</span>';
      heroDesc.textContent = "Eralda tekst, tuvasta keerulised tabelid ja tee skannitud lehtedele automaatne OCR tekstituvastus.";
      heroPillText.textContent = "PyMuPDF ja Microsoft MarkItDown tabelite tuvastus";
    } else if (newMode === "image") {
      heroTitle.innerHTML = 'Piltide EXIF metaandmed & <span class="gradient-text">OCR tekstituvastus</span>';
      heroDesc.textContent = "Ekstraheeri kaamera seaded, GPS asukoht Google Mapsiga ja loe pildilt kogu trükitud tekst Markdowni.";
      heroPillText.textContent = "RapidOCR närvivõrk & täielik EXIF kaamera analüüs";
    }
  }

  modeButtons.forEach((btn) => {
    btn.addEventListener("click", () => switchMode(btn.dataset.mode));
  });

  // =========================================================================
  // 🎬 YOUTUBE TRANSCRIBER LOGIC
  // =========================================================================

  async function fetchVideoInfo(url) {
    const videoId = extractYouTubeId(url);
    if (!videoId || url === lastFetchedUrl) return;
    lastFetchedUrl = url;

    try {
      const resp = await fetch("/api/info", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      const data = await resp.json();
      if (!data.success) return;

      const meta = data.data;
      previewThumb.src = meta.thumbnail;
      previewTitle.textContent = meta.title;
      previewChannel.textContent = meta.channel;
      previewDuration.textContent = meta.duration_formatted;
      previewViews.textContent = `👁️ ${Number(meta.view_count).toLocaleString("et-EE")} vaatamist`;
      previewDate.textContent = meta.upload_date ? `📅 ${meta.upload_date}` : "";
      previewYtLink.href = meta.url;
      previewCard.style.display = "flex";

      if (meta.available_languages && meta.available_languages.length > 0) {
        previewSubsCount.textContent = `💬 ${meta.available_languages.length} keelt saadaval`;
        languageSelect.innerHTML = `<option value="">Automaatne (soovitatav)</option>`;
        meta.available_languages.forEach((lang) => {
          const opt = document.createElement("option");
          opt.value = lang.code;
          opt.textContent = `${lang.name} (${lang.code}) - ${lang.type}`;
          languageSelect.appendChild(opt);
        });
        langHelper.textContent = `Leiti ${meta.available_languages.length} subtiitrite keelevalikut.`;
      } else {
        previewSubsCount.textContent = `💬 Subtiitrite nimekiri puudub (kõne tuvastatakse audiopõhiselt)`;
      }
    } catch (err) {
      console.warn("Info fetch error:", err);
    }
  }

  urlInput.addEventListener("input", () => {
    const val = urlInput.value.trim();
    clearBtn.style.display = val ? "inline-flex" : "none";
    clearTimeout(infoFetchTimeout);
    if (extractYouTubeId(val)) {
      infoFetchTimeout = setTimeout(() => fetchVideoInfo(val), 400);
    } else {
      previewCard.style.display = "none";
      lastFetchedUrl = null;
    }
  });

  pasteBtn.addEventListener("click", async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        urlInput.value = text.trim();
        urlInput.dispatchEvent(new Event("input"));
        showToast("Kleebitud!");
      }
    } catch {
      urlInput.focus();
    }
  });

  clearBtn.addEventListener("click", () => {
    urlInput.value = "";
    clearBtn.style.display = "none";
    previewCard.style.display = "none";
    lastFetchedUrl = null;
    urlInput.focus();
  });

  speechChips.forEach((chip) => {
    chip.addEventListener("click", () => {
      urlInput.value = chip.dataset.url;
      urlInput.dispatchEvent(new Event("input"));
      setTimeout(handleTranscribe, 200);
    });
  });

  timestampsModePills.forEach((pill) => {
    pill.addEventListener("click", () => {
      timestampsModePills.forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");
      const mode = pill.dataset.mode;
      intervalField.style.display = mode === "interval" ? "block" : "none";
    });
  });

  intervalSlider.addEventListener("input", () => {
    intervalDisplay.textContent = `${intervalSlider.value} sekundit`;
  });

  transcribeBtn.addEventListener("click", handleTranscribe);
  urlInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") handleTranscribe();
  });

  async function handleTranscribe() {
    const url = urlInput.value.trim();
    if (!url) {
      showError("Palun sisesta YouTube video link.");
      urlInput.focus();
      return;
    }

    hideError();
    resultsCard.style.display = "none";
    loadingPanel.style.display = "flex";
    transcribeBtn.disabled = true;

    loadingTitle.textContent = "Laadin video andmeid...";
    loadingSub.textContent = "Ühendun YouTube serveritega ja analüüsin kõnerada";

    const stepTimer = setTimeout(() => {
      loadingTitle.textContent = "Transkribeerin ja genereerin Markdowni...";
      loadingSub.textContent = "Microsoft MarkItDown analüüsib kõne ja sünkroniseerib ajatemplid";
    }, 2400);

    const activePill = document.querySelector("#timestamps-mode-group .radio-pill.active");
    const timestampsMode = activePill ? activePill.dataset.mode : "interval";
    const intervalSeconds = parseInt(intervalSlider.value, 10) || 30;
    const selectedLang = languageSelect.value || null;
    const useNative = nativeToggle ? nativeToggle.checked : false;

    try {
      const resp = await fetch("/api/transcribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url,
          language: selectedLang,
          timestamps_mode: timestampsMode,
          interval_seconds: intervalSeconds,
          use_native_markitdown: useNative,
        }),
      });

      clearTimeout(stepTimer);
      const res = await resp.json();
      if (!resp.ok || !res.success) {
        throw new Error(res.detail || "Transkribeerimine ebaõnnestus.");
      }

      currentResult = res.data;
      displayResults(currentResult, "youtube");
      showToast("YouTube konspekt edukalt valmis! ✨");
    } catch (err) {
      clearTimeout(stepTimer);
      showError(err.message || "Tundmatu viga transkribeerimisel.");
    } finally {
      loadingPanel.style.display = "none";
      transcribeBtn.disabled = false;
    }
  }

  // =========================================================================
  // 📄 PDF CONVERTER LOGIC
  // =========================================================================

  pdfDropzone.addEventListener("click", () => pdfFileInput.click());
  pdfDropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    pdfDropzone.classList.add("dragover");
  });
  pdfDropzone.addEventListener("dragleave", () => pdfDropzone.classList.remove("dragover"));
  pdfDropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    pdfDropzone.classList.remove("dragover");
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handlePdfFileSelection(e.dataTransfer.files[0]);
    }
  });

  pdfFileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handlePdfFileSelection(e.target.files[0]);
    }
  });

  function handlePdfFileSelection(file) {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      showError("Valitud fail ei ole PDF fail!");
      return;
    }
    selectedPdfFile = file;
    pdfFileName.textContent = file.name;
    pdfFileSize.textContent = formatBytes(file.size);
    pdfSelectedBox.style.display = "flex";
    hideError();
  }

  pdfRemoveBtn.addEventListener("click", () => {
    selectedPdfFile = null;
    pdfFileInput.value = "";
    pdfSelectedBox.style.display = "none";
  });

  demoPdfBtn.addEventListener("click", async () => {
    hideError();
    resultsCard.style.display = "none";
    loadingPanel.style.display = "flex";
    loadingTitle.textContent = "Genereerin näidis-PDF dokumenti...";
    loadingSub.textContent = "Loome tabelite ja struktuuriga PDF-i ning teisendame selle Markdowniks";

    try {
      const resp = await fetch("/api/demo/pdf");
      const res = await resp.json();
      if (!resp.ok || !res.success) {
        throw new Error(res.detail || "Näidis-PDF genereerimine ebaõnnestus.");
      }
      currentResult = res.data;
      displayResults(currentResult, "pdf");
      showToast("Näidis-PDF teisendatud Markdowniks! ✨");
    } catch (err) {
      showError(err.message || "Näidis-PDF viga.");
    } finally {
      loadingPanel.style.display = "none";
    }
  });

  convertPdfBtn.addEventListener("click", async () => {
    if (!selectedPdfFile) {
      showError("Palun vali või lohista esmalt PDF fail!");
      return;
    }

    hideError();
    resultsCard.style.display = "none";
    loadingPanel.style.display = "flex";
    convertPdfBtn.disabled = true;

    loadingTitle.textContent = "Teisendan PDF faili...";
    loadingSub.textContent = "PyMuPDF ja MarkItDown analüüsivad lehekülgi, tabeleid ja sisu";

    const formData = new FormData();
    formData.append("file", selectedPdfFile);
    formData.append("extract_tables", pdfTablesToggle.checked);
    formData.append("ocr_scanned", pdfOcrToggle.checked);
    formData.append("use_native_markitdown", pdfNativeToggle.checked);

    try {
      const resp = await fetch("/api/convert/pdf", {
        method: "POST",
        body: formData,
      });
      const res = await resp.json();
      if (!resp.ok || !res.success) {
        throw new Error(res.detail || "PDF teisendamine ebaõnnestus.");
      }
      currentResult = res.data;
      displayResults(currentResult, "pdf");
      showToast("PDF edukalt teisendatud Markdowniks! ✨");
    } catch (err) {
      showError(err.message || "PDF teisendamise viga.");
    } finally {
      loadingPanel.style.display = "none";
      convertPdfBtn.disabled = false;
    }
  });

  // =========================================================================
  // 🖼️ IMAGE (EXIF & OCR) LOGIC
  // =========================================================================

  imageDropzone.addEventListener("click", () => imageFileInput.click());
  imageDropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    imageDropzone.classList.add("dragover");
  });
  imageDropzone.addEventListener("dragleave", () => imageDropzone.classList.remove("dragover"));
  imageDropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    imageDropzone.classList.remove("dragover");
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleImageFileSelection(e.dataTransfer.files[0]);
    }
  });

  imageFileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleImageFileSelection(e.target.files[0]);
    }
  });

  function handleImageFileSelection(file) {
    selectedImageFile = file;
    imageFileName.textContent = file.name;
    imageFileSizeBadge.textContent = formatBytes(file.size);

    const imgUrl = URL.createObjectURL(file);
    imagePreviewThumb.src = imgUrl;

    const imgObj = new Image();
    imgObj.onload = () => {
      imageDimensionsBadge.textContent = `${imgObj.naturalWidth} × ${imgObj.naturalHeight} px`;
    };
    imgObj.src = imgUrl;

    imageSelectedBox.style.display = "flex";
    hideError();
  }

  imageRemoveBtn.addEventListener("click", () => {
    selectedImageFile = null;
    imageFileInput.value = "";
    imageSelectedBox.style.display = "none";
  });

  demoImageBtn.addEventListener("click", async () => {
    hideError();
    resultsCard.style.display = "none";
    loadingPanel.style.display = "flex";
    loadingTitle.textContent = "Genereerin näidisfotot...";
    loadingSub.textContent = "Käivitan RapidOCR tekstituvastuse ja analüüsin Sony EXIF / GPS andmeid";

    try {
      const resp = await fetch("/api/demo/image");
      const res = await resp.json();
      if (!resp.ok || !res.success) {
        throw new Error(res.detail || "Näidispildi analüüs ebaõnnestus.");
      }
      currentResult = res.data;
      displayResults(currentResult, "image");
      showToast("Pildi analüüs ja OCR valmis! ✨");
    } catch (err) {
      showError(err.message || "Näidispildi viga.");
    } finally {
      loadingPanel.style.display = "none";
    }
  });

  convertImageBtn.addEventListener("click", async () => {
    if (!selectedImageFile) {
      showError("Palun vali või lohista esmalt pildifail!");
      return;
    }

    hideError();
    resultsCard.style.display = "none";
    loadingPanel.style.display = "flex";
    convertImageBtn.disabled = true;

    loadingTitle.textContent = "Analüüsin pilti ja tuvastan teksti...";
    loadingSub.textContent = "RapidOCR loeb teksti ning Pillow eraldab kaamera ja GPS koordinaadid";

    const formData = new FormData();
    formData.append("file", selectedImageFile);
    formData.append("run_ocr", imageOcrToggle.checked);
    formData.append("extract_exif", imageExifToggle.checked);

    try {
      const resp = await fetch("/api/convert/image", {
        method: "POST",
        body: formData,
      });
      const res = await resp.json();
      if (!resp.ok || !res.success) {
        throw new Error(res.detail || "Pildi analüüs ebaõnnestus.");
      }
      currentResult = res.data;
      displayResults(currentResult, "image");
      showToast("Pildi analüüs ja OCR edukalt lõpetatud! ✨");
    } catch (err) {
      showError(err.message || "Pildi analüüsimise viga.");
    } finally {
      loadingPanel.style.display = "none";
      convertImageBtn.disabled = false;
    }
  });

  // =========================================================================
  // 📊 UNIFIED RESULTS DISPLAY
  // =========================================================================

  function displayResults(data, mode) {
    // Configure Stats Bar
    if (mode === "youtube") {
      statVal1.textContent = Number(data.word_count || 0).toLocaleString("et-EE");
      statLbl1.textContent = "Sõna";
      statVal2.textContent = Number(data.char_count || 0).toLocaleString("et-EE");
      statLbl2.textContent = "Tähemärki";
      statVal3.textContent = `~${data.reading_time_minutes || 1} min`;
      statLbl3.textContent = "Lugemisaeg";
      statVal4.textContent = data.used_engine === "markitdown_native" ? "Native MarkItDown" : "MarkItDown TimedText";
      statLbl4.textContent = "Mootor";

      tabBtnPlain.textContent = "Puhas Tekst";
      tabBtnSrt.style.display = "inline-flex";
      tabBtnMeta.style.display = "none";
      tabBtnStructured.style.display = "none";
      downloadSrtBtn.style.display = "inline-flex";
      srtCode.textContent = data.srt || "";
    } else if (mode === "pdf") {
      statVal1.textContent = data.page_count || 1;
      statLbl1.textContent = "Lehekülge";
      statVal2.textContent = Number(data.word_count || 0).toLocaleString("et-EE");
      statLbl2.textContent = "Sõna";
      statVal3.textContent = data.tables_count || 0;
      statLbl3.textContent = "Tabelit leitud";
      statVal4.textContent = `~${data.reading_time_minutes || 1} min`;
      statLbl4.textContent = "Lugemisaeg";

      tabBtnPlain.textContent = "Puhas Tekst";
      tabBtnSrt.style.display = "none";
      tabBtnMeta.style.display = "inline-flex";
      tabBtnMeta.textContent = "Dokumendi Info";
      downloadSrtBtn.style.display = "none";

      renderPdfMetadata(data.metadata);

      if (data.structured && (data.structured.is_document || (data.structured.key_values && Object.keys(data.structured.key_values).length > 0) || (data.structured.tables && data.structured.tables.length > 0) || (data.structured.spatial_lines && data.structured.spatial_lines.length > 0))) {
        tabBtnStructured.style.display = "inline-flex";
        renderStructuredDocument(data.structured);
      } else {
        tabBtnStructured.style.display = "none";
      }
    } else if (mode === "image") {
      const m = data.metadata;
      statVal1.textContent = `${m.width} × ${m.height}`;
      statLbl1.textContent = "Mõõtmed";
      statVal2.textContent = `${m.megapixels} MP`;
      statLbl2.textContent = "Eraldusvõime";
      statVal3.textContent = Number(data.word_count || 0).toLocaleString("et-EE");
      statLbl3.textContent = "OCR Sõnu";
      statVal4.textContent = m.gps && m.gps.has_gps ? "📍 GPS Olemas" : "Ei ole GPS-i";
      statLbl4.textContent = "Asukoht";

      tabBtnPlain.textContent = "OCR Tekst";
      tabBtnSrt.style.display = "none";
      tabBtnMeta.style.display = "inline-flex";
      tabBtnMeta.textContent = "EXIF & GPS";
      downloadSrtBtn.style.display = "none";

      renderImageMetadata(data.metadata);

      if (data.structured && (data.structured.is_document || (data.structured.key_values && Object.keys(data.structured.key_values).length > 0) || (data.structured.tables && data.structured.tables.length > 0) || (data.structured.spatial_lines && data.structured.spatial_lines.length > 0))) {
        tabBtnStructured.style.display = "inline-flex";
        renderStructuredDocument(data.structured);
      } else {
        tabBtnStructured.style.display = "none";
      }
    } else {
      tabBtnStructured.style.display = "none";
    }

    // Markdown rendered content
    if (window.marked) {
      renderedContent.innerHTML = marked.parse(data.markdown || "");
    } else {
      renderedContent.textContent = data.markdown || "";
    }
    rawMarkdownCode.textContent = data.markdown || "";
    plainTextContent.textContent = data.plain_text || "";

    // Reset tabs to first tab
    resultsTabs.forEach((b) => b.classList.remove("active"));
    const firstTab = document.querySelector("#results-tabs .tab-btn");
    if (firstTab) firstTab.classList.add("active");
    const allPanes = resultsCard.querySelectorAll(".tab-pane");
    allPanes.forEach((p) => p.classList.remove("active"));
    const renderedPane = document.getElementById("tab-rendered");
    if (renderedPane) renderedPane.classList.add("active");

    resultsCard.style.display = "block";
    resultsCard.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function renderPdfMetadata(meta) {
    if (!meta) return;
    let html = '<div class="meta-grid">';

    html += `
      <div class="meta-card">
        <div class="meta-card-title">📄 Dokumendi põhiandmed</div>
        <div class="meta-row"><span class="meta-key">Pealkiri</span><span class="meta-val">${meta.title || "Määramata"}</span></div>
        <div class="meta-row"><span class="meta-key">Autor</span><span class="meta-val">${meta.author || "Teadmata"}</span></div>
        <div class="meta-row"><span class="meta-key">Failinimi</span><span class="meta-val">${meta.filename || ""}</span></div>
        <div class="meta-row"><span class="meta-key">Lehekülgi</span><span class="meta-val">${meta.page_count || 1}</span></div>
        <div class="meta-row"><span class="meta-key">Faili maht</span><span class="meta-val">${meta.file_size_formatted || ""}</span></div>
      </div>
    `;

    if (meta.subject || meta.creation_date) {
      html += `
        <div class="meta-card">
          <div class="meta-card-title">⚙️ Lisainfo & Kuupäevad</div>
          ${meta.subject ? `<div class="meta-row"><span class="meta-key">Teema</span><span class="meta-val">${meta.subject}</span></div>` : ""}
          ${meta.creation_date ? `<div class="meta-row"><span class="meta-key">Loodud</span><span class="meta-val">${meta.creation_date}</span></div>` : ""}
        </div>
      `;
    }

    html += "</div>";

    if (meta.toc && meta.toc.length > 0) {
      html += `
        <div class="meta-card">
          <div class="meta-card-title">📑 Sisukord (Bookmarks)</div>
          ${meta.toc.map((t) => `<div class="meta-row"><span class="meta-key">${t.title}</span><span class="meta-val">lk ${t.page}</span></div>`).join("")}
        </div>
      `;
    }

    metadataViewContainer.innerHTML = html;
  }

  function renderImageMetadata(meta) {
    if (!meta) return;
    const cam = meta.camera || {};
    const gps = meta.gps || {};

    let html = '<div class="meta-grid">';

    // Tech card
    html += `
      <div class="meta-card">
        <div class="meta-card-title">📐 Pildi tehnilised andmed</div>
        <div class="meta-row"><span class="meta-key">Failinimi</span><span class="meta-val">${meta.filename}</span></div>
        <div class="meta-row"><span class="meta-key">Mõõtmed</span><span class="meta-val">${meta.width} × ${meta.height} px</span></div>
        <div class="meta-row"><span class="meta-key">Eraldusvõime</span><span class="meta-val">${meta.megapixels} MP</span></div>
        <div class="meta-row"><span class="meta-key">Kuvasuhe</span><span class="meta-val">${meta.aspect_ratio}</span></div>
        <div class="meta-row"><span class="meta-key">Formaat</span><span class="meta-val">${meta.format} (${meta.mode})</span></div>
        <div class="meta-row"><span class="meta-key">Faili maht</span><span class="meta-val">${meta.file_size_formatted}</span></div>
      </div>
    `;

    // Camera card
    const hasCam = cam.make || cam.model || cam.exposure_time || cam.f_number;
    if (hasCam) {
      html += `
        <div class="meta-card">
          <div class="meta-card-title">📷 Kaamera & EXIF sätted</div>
          ${cam.make || cam.model ? `<div class="meta-row"><span class="meta-key">Kaamera</span><span class="meta-val">${cam.make} ${cam.model}</span></div>` : ""}
          ${cam.lens_model ? `<div class="meta-row"><span class="meta-key">Objektiiv</span><span class="meta-val">${cam.lens_model}</span></div>` : ""}
          ${cam.datetime_original ? `<div class="meta-row"><span class="meta-key">Pildistatud</span><span class="meta-val">${cam.datetime_original}</span></div>` : ""}
          ${cam.exposure_time ? `<div class="meta-row"><span class="meta-key">Säriaeg</span><span class="meta-val">${cam.exposure_time}</span></div>` : ""}
          ${cam.f_number ? `<div class="meta-row"><span class="meta-key">Ava (F-stop)</span><span class="meta-val">${cam.f_number}</span></div>` : ""}
          ${cam.iso ? `<div class="meta-row"><span class="meta-key">ISO</span><span class="meta-val">${cam.iso}</span></div>` : ""}
          ${cam.focal_length ? `<div class="meta-row"><span class="meta-key">Fookuskaugus</span><span class="meta-val">${cam.focal_length}</span></div>` : ""}
        </div>
      `;
    }

    // GPS card
    if (gps.has_gps) {
      html += `
        <div class="meta-card">
          <div class="meta-card-title">📍 Asukoha koordinaadid (GPS)</div>
          <div class="meta-row"><span class="meta-key">Laiuskraad (Lat)</span><span class="meta-val">${gps.latitude}° (${gps.latitude_dms})</span></div>
          <div class="meta-row"><span class="meta-key">Pikkuskraad (Lon)</span><span class="meta-val">${gps.longitude}° (${gps.longitude_dms})</span></div>
          ${gps.altitude_meters ? `<div class="meta-row"><span class="meta-key">Kõrgus merepinnast</span><span class="meta-val">${gps.altitude_meters} m</span></div>` : ""}
          <a href="${gps.google_maps_url}" target="_blank" rel="noopener noreferrer" class="gps-link-btn">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="3 11 22 2 13 21 11 13 3 11"/></svg>
            <span>Ava asukoht Google Mapsis</span>
          </a>
        </div>
      `;
    }

    html += "</div>";
    metadataViewContainer.innerHTML = html;
  }

  function renderStructuredDocument(doc) {
    if (!doc) return;
    const keyVals = doc.key_values || {};
    const tables = doc.tables || [];
    const spatialLines = doc.spatial_lines || [];
    const jsonData = doc.json_data || doc;
    const kvCount = Object.keys(keyVals).length;

    let html = `
      <div class="doc-header-card">
        <div class="doc-type-badge">
          <span>📋</span>
          <span>${doc.document_type || "Tuvastatud dokument"}</span>
        </div>
        <div class="doc-stats-badges">
          <span class="doc-badge-pill">${kvCount} andmevälja</span>
          ${tables.length > 0 ? `<span class="doc-badge-pill">${tables.length} tabelit</span>` : ""}
          ${spatialLines.length > 0 ? `<span class="doc-badge-pill">${spatialLines.length} ruumilist rida</span>` : ""}
          <span class="doc-badge-pill" style="color:#34d399;border-color:rgba(52,211,153,0.3)">JSON Valmis</span>
        </div>
      </div>
    `;

    // Key-Values Grid
    if (kvCount > 0) {
      html += `
        <div class="doc-grid">
          ${Object.entries(keyVals).map(([key, val]) => `
            <div class="doc-field-card" onclick="navigator.clipboard.writeText('${val.replace(/'/g, "\\'")}'); if(window.showToast) window.showToast('Kopeeritud: ${val.replace(/'/g, "\\'")}');" title="Kliki kopeerimiseks">
              <div class="doc-field-key">
                <span>${key}</span>
                <span class="doc-field-copy-hint">Kliki kopeerimiseks</span>
              </div>
              <div class="doc-field-val">${val}</div>
            </div>
          `).join("")}
        </div>
      `;
    }

    // Tables
    if (tables.length > 0) {
      tables.forEach((tbl, idx) => {
        const headers = tbl.headers || [];
        const rows = tbl.rows || [];
        if (headers.length > 0 || rows.length > 0) {
          html += `
            <div class="doc-table-card">
              <div class="doc-table-title">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3h18v18H3z"/><path d="M3 9h18"/><path d="M3 15h18"/><path d="M9 3v18"/><path d="M15 3v18"/></svg>
                <span>Tuvastatud tabel #${idx + 1} (${rows.length} rida)</span>
              </div>
              <table class="doc-data-table">
                <thead>
                  <tr>
                    ${headers.map((h) => `<th>${h}</th>`).join("")}
                  </tr>
                </thead>
                <tbody>
                  ${rows.map((r) => `
                    <tr>
                      ${r.map((c) => `<td>${c}</td>`).join("")}
                    </tr>
                  `).join("")}
                </tbody>
              </table>
            </div>
          `;
        }
      });
    }

    // 2D Spatial Layout
    if (spatialLines.length > 1) {
      const spatialEscaped = spatialLines.join("\n")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
      html += `
        <div class="doc-spatial-card">
          <div class="doc-spatial-header">
            <div class="doc-spatial-title">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
              <span>2D Ruumiline Paigutus (Veerud ja read)</span>
            </div>
            <button class="prompt-copy-btn" id="copy-spatial-btn" type="button">Kopeeri paigutus</button>
          </div>
          <pre class="doc-spatial-pre"><code>${spatialEscaped}</code></pre>
        </div>
      `;
    }

    // JSON Structure Card
    const jsonFormatted = JSON.stringify(jsonData, null, 2);
    html += `
      <div class="doc-json-card">
        <div class="doc-json-header">
          <div class="doc-json-title">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
            <span>Struktureeritud JSON Väljund</span>
          </div>
          <button class="prompt-copy-btn" id="copy-json-btn" type="button">Kopeeri JSON</button>
        </div>
        <pre class="json-pre-block"><code>${jsonFormatted.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")}</code></pre>
      </div>
    `;

    structuredViewContainer.innerHTML = html;

    const copyJsonBtn = document.getElementById("copy-json-btn");
    if (copyJsonBtn) {
      copyJsonBtn.addEventListener("click", () => {
        navigator.clipboard.writeText(jsonFormatted).then(() => {
          showToast("JSON andmed kopeeritud lõikelauale! 📋");
        });
      });
    }

    const copySpatialBtn = document.getElementById("copy-spatial-btn");
    if (copySpatialBtn) {
      copySpatialBtn.addEventListener("click", () => {
        navigator.clipboard.writeText(spatialLines.join("\n")).then(() => {
          showToast("2D paigutus kopeeritud lõikelauale! 📋");
        });
      });
    }
  }

  // --- Tab Navigation ---
  resultsTabs.forEach((btn) => {
    btn.addEventListener("click", () => {
      resultsTabs.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");

      const targetId = btn.dataset.tab;
      const allPanes = resultsCard.querySelectorAll(".tab-pane");
      allPanes.forEach((p) => p.classList.remove("active"));

      const targetPane = document.getElementById(targetId);
      if (targetPane) targetPane.classList.add("active");
    });
  });

  // --- Copy & Export ---
  copyBtn.addEventListener("click", () => {
    if (!currentResult) return;
    const activeTab = document.querySelector("#results-tabs .tab-btn.active");
    const tabName = activeTab ? activeTab.dataset.tab : "tab-rendered";

    let textToCopy = currentResult.markdown || "";
    if (tabName === "tab-plain") textToCopy = currentResult.plain_text || "";
    else if (tabName === "tab-srt") textToCopy = currentResult.srt || "";
    else if (tabName === "tab-structured") {
      const jData = (currentResult.structured && currentResult.structured.json_data) ? currentResult.structured.json_data : currentResult.structured;
      textToCopy = JSON.stringify(jData || currentResult, null, 2);
    }

    navigator.clipboard.writeText(textToCopy).then(() => {
      showToast("Kopeeritud lõikelauale!");
    });
  });

  if (downloadJsonBtn) {
    downloadJsonBtn.addEventListener("click", () => {
      if (!currentResult) return;
      let exportObj = currentResult;
      if (currentResult.structured && currentResult.structured.json_data && Object.keys(currentResult.structured.json_data).length > 0) {
        exportObj = currentResult.structured.json_data;
      }
      const jsonStr = JSON.stringify(exportObj, null, 2);
      const fname = getDownloadBaseName() + ".json";
      downloadFile(jsonStr, fname, "application/json;charset=utf-8");
    });
  }

  downloadMdBtn.addEventListener("click", () => {
    if (!currentResult) return;
    const fname = getDownloadBaseName() + ".md";
    downloadFile(currentResult.markdown, fname, "text/markdown;charset=utf-8");
  });

  downloadTxtBtn.addEventListener("click", () => {
    if (!currentResult) return;
    const fname = getDownloadBaseName() + ".txt";
    downloadFile(currentResult.plain_text, fname, "text/plain;charset=utf-8");
  });

  downloadSrtBtn.addEventListener("click", () => {
    if (!currentResult || !currentResult.srt) return;
    const fname = getDownloadBaseName() + ".srt";
    downloadFile(currentResult.srt, fname, "text/plain;charset=utf-8");
  });

  function getDownloadBaseName() {
    if (!currentResult) return "tulemus";
    if (currentMode === "youtube") {
      return `transkriptsioon_${(currentResult.metadata && currentResult.metadata.video_id) || "video"}`;
    } else if (currentMode === "pdf") {
      return `pdf_${(currentResult.metadata && currentResult.metadata.filename) || "dokument"}`;
    } else {
      return `pilt_${(currentResult.metadata && currentResult.metadata.filename) || "analuus"}`;
    }
  }

  function downloadFile(content, filename, mimeType) {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }, 150);
    showToast(`Fail '${filename}' laaditakse alla!`);
  }

  // --- AI Prompts Integration ---
  promptCopyBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      if (!currentResult) {
        showToast("Esmalt teisenda materjal!", true);
        return;
      }
      const type = btn.dataset.type;
      const card = btn.closest(".prompt-card");
      const promptTextEl = card ? card.querySelector(".prompt-text") : null;
      const basePrompt = promptTextEl ? promptTextEl.textContent.replace(/^"|"$/g, "") : "";

      const content = currentResult.markdown || currentResult.plain_text;
      const fullText = `${basePrompt}\n\n---\n\n${content}`;

      navigator.clipboard.writeText(fullText).then(() => {
        showToast("Prompt koos Markdown sisuga kopeeritud! 📋");
      });
    });
  });

  // --- Batch Mode Logic ---
  batchToggleBtn.addEventListener("click", () => {
    batchModal.style.display = "flex";
  });

  batchCloseBtn.addEventListener("click", () => {
    batchModal.style.display = "none";
  });

  batchModal.addEventListener("click", (e) => {
    if (e.target === batchModal) batchModal.style.display = "none";
  });

  batchStartBtn.addEventListener("click", async () => {
    const text = batchUrlsInput.value.trim();
    if (!text) {
      showToast("Sisesta vähemalt üks link!", true);
      return;
    }

    const urls = text.split("\n").map((u) => u.trim()).filter((u) => u.length > 0);
    if (urls.length === 0) return;

    batchStartBtn.disabled = true;
    batchResultsList.style.display = "block";
    batchResultsList.innerHTML = `<p style="color: #a5b4fc; padding: 10px;">Töötlen ${urls.length} videot...</p>`;

    try {
      const resp = await fetch("/api/batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ urls }),
      });
      const data = await resp.json();
      if (!data.success) throw new Error("Hulgitöötlus ebaõnnestus.");

      batchResultsList.innerHTML = "";
      data.items.forEach((item) => {
        const div = document.createElement("div");
        div.className = "batch-item-result";
        if (item.success) {
          div.innerHTML = `
            <span style="color: #34d399; font-weight: bold;">✓ ${item.title || item.video_id}</span>
            <span style="font-size: 0.8rem; color: #94a3b8;">(${item.word_count} sõna)</span>
          `;
        } else {
          div.innerHTML = `
            <span style="color: #f87171;">✗ ${item.url}</span>
            <span style="font-size: 0.8rem; color: #fca5a5;">${item.error}</span>
          `;
        }
        batchResultsList.appendChild(div);
      });
      showToast("Hulgitöötlus lõpetatud!");
    } catch (err) {
      batchResultsList.innerHTML = `<p style="color: #f87171;">Viga: ${err.message}</p>`;
    } finally {
      batchStartBtn.disabled = false;
    }
  });

  errorClose.addEventListener("click", hideError);
});
