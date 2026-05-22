# 🚀 Jhatpat Downloader

![Jhatpat Downloader](logo.png)

**Jhatpat Downloader** is a lightning-fast, beautifully designed, and feature-rich media extraction tool. Built with a powerful Python backend and a companion Chrome Extension (**Jhatpat Scout**), it seamlessly captures and organizes high-quality media directly from your browser.

---

## ✨ Key Features

- **The Media Scout Extension:** A dedicated Chrome extension that acts as a radar, sniffing out high-res images, streaming video URLs, audio files, and subtitles across the web.
- **Smart Session Folders:** Automatically groups your downloaded media into neat, organized subfolders based on the webpage title or YouTube playlist name. 
- **Batch Downloading:** Select multiple videos, audio tracks, or 4K images via the extension and download them all at once.
- **Direct Asset Download Engine:** A built-in, lightweight downloader designed exclusively to grab images and subtitles without overhead, while dedicating `yt-dlp` strictly to complex audio/video streams.
- **Dynamic UI:** A stunning CustomTkinter interface with animated radar visuals, dark-mode aesthetics, download queues, and real-time progress tracking.
- **Format Flexibility:** Extract audio into pristine 320kbps MP3s or download videos ranging from 480p up to stunning 4K resolution.

---

## 🛠️ Technology Stack

- **Backend:** Python 3, Flask (API routing), `yt-dlp` (Stream extraction), `requests` (Direct downloading)
- **Frontend / UI:** `CustomTkinter`
- **Browser Extension:** Vanilla JavaScript, HTML, CSS (Manifest V3)
- **Compilation:** `PyInstaller` & `Inno Setup` for the final distributable executable.

---

## 🚀 How to Use

### 1. The Desktop App
- Launch `JhatpatDownloader.exe`.
- Paste any supported media URL into the search bar, or let the automatic clipboard listener catch it for you.
- Choose your preferred resolution and format, then hit download. 

### 2. The Jhatpat Scout Extension
- Install the extension in Chrome (Load Unpacked -> Select `Jhatpat_Scout` folder).
- Browse to any webpage containing media (like a YouTube playlist or a stock image gallery).
- Click the Jhatpat Scout icon to reveal the partitioned dashboard showing all discovered Videos, Audio, Images, and Subtitles.
- Select what you want to keep and click "Download Selected" to instantly send them to the desktop app!

---

*Created by Kakdamba.*
