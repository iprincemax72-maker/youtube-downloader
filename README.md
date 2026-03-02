# YouTube Downloader

A simple desktop app to download YouTube videos and audio.

## Download

Go to the **[Latest Release](https://github.com/iprincemax72-maker/youtube-downloader/releases/latest)** page.

### Windows

1. Download **`YouTubeDownloader-Windows.zip`** from the release
2. Extract the zip file
3. Open the extracted folder and double-click **`YouTube Downloader.exe`**
4. If Windows shows "Windows protected your PC" — click **More info** then **Run anyway** (this is normal for unsigned apps)

### Mac

1. Download **`YouTubeDownloader-macOS.zip`** from the release
2. Extract the zip file
3. Drag **`YouTube Downloader.app`** to your Applications folder
4. Right-click the app and click **Open** the first time (macOS blocks unsigned apps by default)

## Features

- Paste a YouTube link and hit Download
- Pick quality: Best, 4K, 1440p, 1080p, 720p, 480p
- **Audio Only** — downloads as MP3 (320kbps)
- **Video Only** — downloads video without sound
- All video downloads are automatically H.264 for editing software compatibility (Premiere Pro, DaVinci Resolve, etc.)
- **Show in Finder / Explorer** — opens the downloaded file location
- Cancel downloads anytime
- Mac menu bar icon for quick downloads

## Requirements

- **Windows**: Windows 10 or later (ffmpeg is bundled)
- **Mac**: macOS 11+ with [ffmpeg](https://brew.sh) installed (`brew install ffmpeg`)
