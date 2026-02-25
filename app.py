#!/usr/bin/env python3
"""YouTube Video Downloader — Desktop GUI App (up to 4K, Premiere Pro compatible)."""

import os
import platform
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog

import certifi
import customtkinter as ctk
import yt_dlp

# Fix SSL certificates on macOS
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

QUALITY_MAP = {
    "Best":   "bestvideo[vcodec^=avc]+bestaudio[acodec^=mp4a]/bestvideo+bestaudio/best",
    "4K":     "bestvideo[height<=2160][vcodec^=avc]/bestvideo[height<=2160]+bestaudio[acodec^=mp4a]/bestaudio/best[height<=2160]",
    "1440p":  "bestvideo[height<=1440][vcodec^=avc]/bestvideo[height<=1440]+bestaudio[acodec^=mp4a]/bestaudio/best[height<=1440]",
    "1080p":  "bestvideo[height<=1080][vcodec^=avc]/bestvideo[height<=1080]+bestaudio[acodec^=mp4a]/bestaudio/best[height<=1080]",
    "720p":   "bestvideo[height<=720][vcodec^=avc]/bestvideo[height<=720]+bestaudio[acodec^=mp4a]/bestaudio/best[height<=720]",
    "480p":   "bestvideo[height<=480][vcodec^=avc]/bestvideo[height<=480]+bestaudio[acodec^=mp4a]/bestaudio/best[height<=480]",
}


def get_ffmpeg_path():
    """Return the path to bundled ffmpeg/ffprobe or fall back to system PATH."""
    if getattr(sys, "frozen", False):
        # Running as PyInstaller bundle
        base = sys._MEIPASS
        if platform.system() == "Windows":
            ff = os.path.join(base, "ffmpeg.exe")
            fp = os.path.join(base, "ffprobe.exe")
        else:
            ff = os.path.join(base, "ffmpeg")
            fp = os.path.join(base, "ffprobe")
        if os.path.exists(ff):
            return ff, fp
    return "ffmpeg", "ffprobe"


FFMPEG, FFPROBE = get_ffmpeg_path()


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("YouTube Downloader")
        # Center the window on screen
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        win_w, win_h = 620, 520
        x = (screen_w - win_w) // 2
        y = (screen_h - win_h) // 2
        self.geometry(f"{win_w}x{win_h}+{x}+{y}")
        self.resizable(False, False)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self._downloading = False
        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 20, "pady": (8, 0)}

        # --- URL ---
        ctk.CTkLabel(self, text="YouTube URL", anchor="w").pack(fill="x", **pad)
        self.url_entry = ctk.CTkEntry(self, placeholder_text="https://www.youtube.com/watch?v=...")
        self.url_entry.pack(fill="x", padx=20, pady=(4, 0))

        # --- Quality picker ---
        ctk.CTkLabel(self, text="Quality", anchor="w").pack(fill="x", **pad)
        self.quality_var = ctk.StringVar(value="Best")
        self.quality_menu = ctk.CTkOptionMenu(
            self, variable=self.quality_var,
            values=list(QUALITY_MAP.keys()),
            width=200,
        )
        self.quality_menu.pack(anchor="w", padx=20, pady=(4, 0))

        # --- Toggles row ---
        toggle_frame = ctk.CTkFrame(self, fg_color="transparent")
        toggle_frame.pack(fill="x", padx=20, pady=(14, 0))

        self.premiere_var = ctk.BooleanVar(value=False)
        self.premiere_switch = ctk.CTkSwitch(
            toggle_frame, text="Premiere Pro compatible",
            variable=self.premiere_var,
        )
        self.premiere_switch.pack(side="left", padx=(0, 30))

        self.audio_var = ctk.BooleanVar(value=False)
        self.audio_switch = ctk.CTkSwitch(
            toggle_frame, text="Audio only (MP3 320kbps)",
            variable=self.audio_var, command=self._on_audio_toggle,
        )
        self.audio_switch.pack(side="left")

        # --- Output folder ---
        ctk.CTkLabel(self, text="Output Folder", anchor="w").pack(fill="x", **pad)
        folder_frame = ctk.CTkFrame(self, fg_color="transparent")
        folder_frame.pack(fill="x", padx=20, pady=(4, 0))

        default_dl = os.path.join(os.path.expanduser("~"), "Downloads")
        self.folder_var = ctk.StringVar(value=default_dl)
        self.folder_entry = ctk.CTkEntry(folder_frame, textvariable=self.folder_var)
        self.folder_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(folder_frame, text="Browse", width=80, command=self._browse).pack(side="left")

        # --- Download button ---
        self.dl_button = ctk.CTkButton(
            self, text="Download", height=42, font=ctk.CTkFont(size=15, weight="bold"),
            command=self._start_download,
        )
        self.dl_button.pack(fill="x", padx=20, pady=(20, 0))

        # --- Progress bar ---
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.pack(fill="x", padx=20, pady=(16, 0))
        self.progress_bar.set(0)

        # --- Status text ---
        self.status_label = ctk.CTkLabel(
            self, text="Ready", anchor="w",
            font=ctk.CTkFont(size=12), text_color="gray",
        )
        self.status_label.pack(fill="x", padx=20, pady=(6, 0))

        # --- Title display ---
        self.title_label = ctk.CTkLabel(
            self, text="", anchor="w", wraplength=560,
            font=ctk.CTkFont(size=12),
        )
        self.title_label.pack(fill="x", padx=20, pady=(4, 10))

    # --- UI callbacks ---

    def _browse(self):
        path = filedialog.askdirectory(initialdir=self.folder_var.get())
        if path:
            self.folder_var.set(path)

    def _on_audio_toggle(self):
        if self.audio_var.get():
            self.quality_menu.configure(state="disabled")
            self.premiere_switch.configure(state="disabled")
        else:
            self.quality_menu.configure(state="normal")
            self.premiere_switch.configure(state="normal")

    def _set_status(self, text):
        self.status_label.configure(text=text)

    def _set_progress(self, value):
        self.progress_bar.set(value)

    # --- Download logic ---

    def _start_download(self):
        url = self.url_entry.get().strip()
        if not url:
            self._set_status("Please enter a YouTube URL.")
            return
        if self._downloading:
            return

        self._downloading = True
        self.dl_button.configure(state="disabled", text="Downloading...")
        self._set_progress(0)
        self._set_status("Starting download...")
        self.title_label.configure(text="")

        thread = threading.Thread(target=self._download_thread, args=(url,), daemon=True)
        thread.start()

    def _download_thread(self, url):
        try:
            output_dir = self.folder_var.get()
            audio_only = self.audio_var.get()
            premiere = self.premiere_var.get()
            quality = self.quality_var.get()

            if audio_only:
                fmt = "bestaudio/best"
                postprocessors = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "320",
                }]
            else:
                fmt = QUALITY_MAP.get(quality, QUALITY_MAP["Best"])
                postprocessors = []

            opts = {
                "format": fmt,
                "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
                "merge_output_format": "mp4" if not audio_only else None,
                "progress_hooks": [self._progress_hook],
                "postprocessors": postprocessors,
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "ffmpeg_location": os.path.dirname(FFMPEG) if os.path.sep in FFMPEG else None,
            }
            # Remove None values
            opts = {k: v for k, v in opts.items() if v is not None}

            with yt_dlp.YoutubeDL(opts) as ydl:
                self.after(0, self._set_status, "Fetching video info...")
                info = ydl.extract_info(url, download=False)
                title = info.get("title", "Unknown")
                duration = info.get("duration_string", "?")
                self.after(0, self.title_label.configure, {"text": f"{title}  ({duration})"})
                self.after(0, self._set_status, "Downloading...")

                ydl.download([url])

                # Premiere Pro re-encode if needed
                if not audio_only and premiere:
                    filename = ydl.prepare_filename(info)
                    base, _ = os.path.splitext(filename)
                    mp4_path = base + ".mp4"
                    if os.path.exists(mp4_path):
                        codec = self._get_video_codec(mp4_path)
                        if codec and codec != "h264":
                            self.after(0, self._set_status, f"Re-encoding to H.264 (was {codec})...")
                            self.after(0, self._set_progress, 0.5)
                            self._reencode_to_h264(mp4_path)

            self.after(0, self._set_progress, 1.0)
            self.after(0, self._set_status, f"Done! Saved to {output_dir}")

        except Exception as e:
            self.after(0, self._set_status, f"Error: {e}")
            self.after(0, self._set_progress, 0)
        finally:
            self._downloading = False
            self.after(0, self.dl_button.configure, {"state": "normal", "text": "Download"})

    def _progress_hook(self, d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded = d.get("downloaded_bytes", 0)
            if total and total > 0:
                pct = downloaded / total
                self.after(0, self._set_progress, pct)
            speed = d.get("_speed_str", "")
            eta = d.get("_eta_str", "")
            pct_str = d.get("_percent_str", "")
            self.after(0, self._set_status, f"Downloading {pct_str}   Speed: {speed}   ETA: {eta}")
        elif d["status"] == "finished":
            self.after(0, self._set_status, "Merging streams...")
            self.after(0, self._set_progress, 0.95)

    @staticmethod
    def _get_video_codec(filepath):
        cmd = [
            FFPROBE, "-v", "quiet", "-select_streams", "v:0",
            "-show_entries", "stream=codec_name", "-of", "csv=p=0",
            filepath,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout.strip()

    @staticmethod
    def _reencode_to_h264(filepath):
        tmp_path = filepath + ".tmp.mp4"
        cmd = [
            FFMPEG, "-y", "-i", filepath,
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-c:a", "aac", "-b:a", "256k",
            "-movflags", "+faststart",
            "-pix_fmt", "yuv420p",
            tmp_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            os.replace(tmp_path, filepath)
        else:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


if __name__ == "__main__":
    app = App()
    app.mainloop()
