#!/usr/bin/env python3
"""YouTube Downloader — unified menu bar + GUI app."""

import os
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog

import platform
import sys

import certifi

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

IS_WINDOWS = platform.system() == "Windows"

# Find ffmpeg: bundled (PyInstaller) or system paths
if getattr(sys, 'frozen', False):
    # Running as PyInstaller bundle — ffmpeg is next to the exe
    FFMPEG_DIR = sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.dirname(sys.executable)
else:
    FFMPEG_DIR = ""

# Ensure ffmpeg is findable
for p in [FFMPEG_DIR, "/opt/homebrew/bin", "/usr/local/bin"]:
    if p and p not in os.environ.get("PATH", ""):
        sep = ";" if IS_WINDOWS else ":"
        os.environ["PATH"] = p + sep + os.environ.get("PATH", "")

import customtkinter as ctk
import yt_dlp

DOWNLOAD_DIR = os.path.expanduser("~/Downloads")

QUALITY_MAP = {
    "Best":   "bestvideo+bestaudio/best",
    "4K":     "bestvideo[height<=2160]+bestaudio/best[height<=2160]/bestvideo+bestaudio/best",
    "1440p":  "bestvideo[height<=1440]+bestaudio/best[height<=1440]/bestvideo+bestaudio/best",
    "1080p":  "bestvideo[height<=1080]+bestaudio/best[height<=1080]/bestvideo+bestaudio/best",
    "720p":   "bestvideo[height<=720]+bestaudio/best[height<=720]/bestvideo+bestaudio/best",
    "480p":   "bestvideo[height<=480]+bestaudio/best[height<=480]/bestvideo+bestaudio/best",
}

FORMAT = QUALITY_MAP["Best"]

# Global reference to the tkinter app so the menu bar can talk to it
_app = None


def setup_menubar():
    """Create the macOS status bar icon + dropdown menu."""
    try:
        from AppKit import (
            NSStatusBar, NSVariableStatusItemLength, NSMenu, NSMenuItem,
            NSImage, NSObject,
        )
        from Foundation import NSObject as FNSObject
        import objc

        class MenuDelegate(NSObject):
            @objc.python_method
            def _quick_download(self):
                from AppKit import NSAlert, NSTextField, NSAlertFirstButtonReturn
                alert = NSAlert.alloc().init()
                alert.setMessageText_("Quick Download")
                alert.setInformativeText_("Paste a YouTube URL:")
                alert.addButtonWithTitle_("Download")
                alert.addButtonWithTitle_("Cancel")
                tf = NSTextField.alloc().initWithFrame_(((0, 0), (400, 24)))
                tf.setPlaceholderString_("https://www.youtube.com/watch?v=...")
                alert.setAccessoryView_(tf)
                alert.window().setInitialFirstResponder_(tf)
                if alert.runModal() == NSAlertFirstButtonReturn:
                    url = str(tf.stringValue()).strip()
                    if url:
                        threading.Thread(target=self._do_download, args=(url,), daemon=True).start()

            @objc.python_method
            def _do_download(self, url):
                try:
                    os.system('osascript -e \'display notification "Starting download..." with title "YouTube Downloader"\'')
                    opts = {
                        "format": FORMAT,
                        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
                        "merge_output_format": "mp4",
                        "noplaylist": True, "quiet": True, "no_warnings": True,
                        "ffmpeg_location": FFMPEG_DIR,
                    }
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        info = ydl.extract_info(url, download=False)
                        title = info.get("title", "Video")
                        ydl.download([url])
                        os.system(f'osascript -e \'display notification "{title}" with title "Download complete!"\'')
                except Exception as e:
                    msg = str(e)[:80].replace("'", "")
                    os.system(f'osascript -e \'display notification "{msg}" with title "Download failed"\'')

            def doQuickDownload_(self, sender):
                self._quick_download()

            def doOpenApp_(self, sender):
                global _app
                if _app:
                    _app.deiconify()
                    _app.lift()
                    _app.focus_force()

            def doQuit_(self, sender):
                global _app
                if _app:
                    _app.quit()

        delegate = MenuDelegate.alloc().init()

        status_bar = NSStatusBar.systemStatusBar()
        item = status_bar.statusItemWithLength_(NSVariableStatusItemLength)

        image = NSImage.imageWithSystemSymbolName_accessibilityDescription_(
            "arrow.down.circle.fill", "Download")
        if image:
            image.setTemplate_(True)
            item.button().setImage_(image)
        else:
            item.button().setTitle_("DL")

        menu = NSMenu.alloc().init()

        mi_quick = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Quick Download", "doQuickDownload:", "")
        mi_quick.setTarget_(delegate)
        menu.addItem_(mi_quick)

        menu.addItem_(NSMenuItem.separatorItem())

        mi_open = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Open Full App", "doOpenApp:", "")
        mi_open.setTarget_(delegate)
        menu.addItem_(mi_open)

        menu.addItem_(NSMenuItem.separatorItem())

        mi_quit = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Quit", "doQuit:", "")
        mi_quit.setTarget_(delegate)
        menu.addItem_(mi_quit)

        item.setMenu_(menu)

        # Keep references alive so they don't get garbage collected
        setup_menubar._refs = (item, menu, delegate)
        return True
    except Exception:
        return False


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("YouTube Downloader")
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
        self._cancelled = False
        self._download_id = 0
        self._last_downloaded_file = None
        self._build_ui()

        # Set up menu bar icon after tkinter is initialized (macOS only)
        self._has_menubar = False
        if not IS_WINDOWS:
            self._has_menubar = setup_menubar()
        if self._has_menubar:
            self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        self.withdraw()

    def _build_ui(self):
        px = 24

        # ── URL ──
        ctk.CTkLabel(self, text="Paste a YouTube link", anchor="w",
                     font=ctk.CTkFont(size=13), text_color="gray").pack(fill="x", padx=px, pady=(14, 0))
        self.url_entry = ctk.CTkEntry(self, height=40, corner_radius=10,
                                       placeholder_text="https://www.youtube.com/watch?v=...")
        self.url_entry.pack(fill="x", padx=px, pady=(4, 0))

        # ── Quality + Switches (same row) ──
        options_row = ctk.CTkFrame(self, fg_color="transparent")
        options_row.pack(fill="x", padx=px, pady=(16, 0))

        quality_frame = ctk.CTkFrame(options_row, fg_color="transparent")
        quality_frame.pack(side="left", padx=(0, 20))
        ctk.CTkLabel(quality_frame, text="Quality", anchor="w",
                     font=ctk.CTkFont(size=13), text_color="gray").pack(anchor="w")
        self.quality_var = ctk.StringVar(value="Best")
        self.quality_menu = ctk.CTkOptionMenu(
            quality_frame, variable=self.quality_var,
            values=list(QUALITY_MAP.keys()), width=150, height=32, corner_radius=8)
        self.quality_menu.pack(anchor="w", pady=(4, 0))

        switch_frame = ctk.CTkFrame(options_row, fg_color="transparent")
        switch_frame.pack(side="left", fill="y")

        self.audio_only_var = ctk.BooleanVar(value=False)
        self.audio_only_switch = ctk.CTkSwitch(switch_frame, text="Audio Only (MP3)",
                                                variable=self.audio_only_var,
                                                command=self._on_audio_only_toggle)
        self.audio_only_switch.pack(anchor="w", pady=(6, 0))

        self.video_only_var = ctk.BooleanVar(value=False)
        self.video_only_switch = ctk.CTkSwitch(switch_frame, text="Video Only (No Sound)",
                                                variable=self.video_only_var,
                                                command=self._on_video_only_toggle)
        self.video_only_switch.pack(anchor="w", pady=(4, 0))

        # ── Save to ──
        ctk.CTkLabel(self, text="Save to", anchor="w",
                     font=ctk.CTkFont(size=13), text_color="gray").pack(fill="x", padx=px, pady=(16, 0))
        folder_row = ctk.CTkFrame(self, fg_color="transparent")
        folder_row.pack(fill="x", padx=px, pady=(4, 0))
        self.folder_var = ctk.StringVar(value=DOWNLOAD_DIR)
        self.folder_entry = ctk.CTkEntry(folder_row, textvariable=self.folder_var,
                                          height=34, corner_radius=8)
        self.folder_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(folder_row, text="Browse", width=80, height=34,
                      corner_radius=8, fg_color="gray30", hover_color="gray40",
                      command=self._browse).pack(side="left")

        # ── Download / Cancel / New ──
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=px, pady=(22, 0))

        self.dl_button = ctk.CTkButton(
            btn_frame, text="Download", height=48, corner_radius=12,
            font=ctk.CTkFont(size=16, weight="bold"),
            command=self._start_download)
        self.dl_button.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.cancel_button = ctk.CTkButton(
            btn_frame, text="Cancel", width=90, height=48, corner_radius=12,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#cc0000", hover_color="#990000", state="disabled",
            command=self._cancel_download)
        self.cancel_button.pack(side="left", padx=(0, 6))

        self.again_button = ctk.CTkButton(
            btn_frame, text="New", width=70, height=48, corner_radius=12,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#2d8a4e", hover_color="#1e6b3a",
            command=self._reset)
        self.again_button.pack(side="left")

        # ── Show in Finder (right below download) ──
        show_text = "Show in Explorer" if IS_WINDOWS else "Show in Finder"
        self.show_button = ctk.CTkButton(
            self, text=show_text, height=36, corner_radius=10,
            font=ctk.CTkFont(size=13),
            fg_color="gray30", hover_color="gray40",
            command=self._show_in_finder)
        self.show_button.pack(fill="x", padx=px, pady=(8, 0))

        # ── Progress ──
        self.progress_bar = ctk.CTkProgressBar(self, height=6, corner_radius=3)
        self.progress_bar.pack(fill="x", padx=px, pady=(18, 0))
        self.progress_bar.set(0)

        self.title_label = ctk.CTkLabel(self, text="", anchor="w", wraplength=560,
                                         font=ctk.CTkFont(size=12))
        self.title_label.pack(fill="x", padx=px, pady=(8, 0))

        self.status_label = ctk.CTkLabel(self, text="Ready", anchor="w",
                                          font=ctk.CTkFont(size=12), text_color="gray")
        self.status_label.pack(fill="x", padx=px, pady=(2, 16))

    def _on_audio_only_toggle(self):
        if self.audio_only_var.get():
            self.video_only_var.set(False)
            self.quality_menu.configure(state="disabled")
        else:
            self.quality_menu.configure(state="normal")

    def _on_video_only_toggle(self):
        if self.video_only_var.get():
            self.audio_only_var.set(False)
            self.quality_menu.configure(state="normal")

    def _browse(self):
        path = filedialog.askdirectory(initialdir=self.folder_var.get())
        if path:
            self.folder_var.set(path)

    def _set_status(self, text):
        self.status_label.configure(text=text)

    def _set_progress(self, value):
        self.progress_bar.set(value)

    def _show_in_finder(self):
        if IS_WINDOWS:
            if self._last_downloaded_file and os.path.exists(self._last_downloaded_file):
                subprocess.Popen(["explorer", "/select,", self._last_downloaded_file])
            else:
                subprocess.Popen(["explorer", self.folder_var.get()])
        else:
            if self._last_downloaded_file and os.path.exists(self._last_downloaded_file):
                subprocess.Popen(["open", "-R", self._last_downloaded_file])
            else:
                subprocess.Popen(["open", self.folder_var.get()])

    def _reset(self):
        if self._downloading:
            return
        self.url_entry.delete(0, "end")
        self._set_progress(0)
        self._set_status("Ready")
        self.title_label.configure(text="")
        self._last_downloaded_file = None
        self.url_entry.focus()

    def _cancel_download(self):
        self._download_id += 1  # abandon current thread
        self._downloading = False
        self._cancelled = True
        self._set_status("Cancelled.")
        self._set_progress(0)
        self.dl_button.configure(state="normal", text="Download")
        self.cancel_button.configure(state="disabled")

    def _start_download(self):
        url = self.url_entry.get().strip()
        if not url:
            self._set_status("Please enter a YouTube URL.")
            return
        if self._downloading:
            return
        self._downloading = True
        self._cancelled = False
        self._download_id += 1
        self.dl_button.configure(state="disabled", text="Downloading...")
        self.cancel_button.configure(state="normal")
        self._set_progress(0)
        self._set_status("Fetching video info...")
        self.title_label.configure(text="")
        threading.Thread(target=self._download_thread, args=(url, self._download_id), daemon=True).start()

    def _download_thread(self, url, my_id):
        import glob, time
        try:
            output_dir = self.folder_var.get()
            quality = self.quality_var.get()
            audio_only = self.audio_only_var.get()
            video_only = self.video_only_var.get()

            if audio_only:
                fmt = "bestaudio/best"
                postprocessors = [{"key": "FFmpegExtractAudio",
                                   "preferredcodec": "mp3", "preferredquality": "320"}]
            elif video_only:
                base = QUALITY_MAP.get(quality, QUALITY_MAP["Best"])
                fmt = base.split("+")[0]
                postprocessors = []
            else:
                fmt = QUALITY_MAP.get(quality, QUALITY_MAP["Best"])
                postprocessors = []

            def progress_hook(d):
                if self._download_id != my_id:
                    raise Exception("cancelled")
                if d["status"] == "downloading":
                    total = d.get("total_bytes") or d.get("total_bytes_estimate")
                    downloaded = d.get("downloaded_bytes", 0)
                    if total and total > 0:
                        self.after(0, self._set_progress, downloaded / total)
                    speed = d.get("_speed_str", "")
                    eta = d.get("_eta_str", "")
                    pct_str = d.get("_percent_str", "")
                    self.after(0, self._set_status, f"Downloading {pct_str}   Speed: {speed}   ETA: {eta}")
                elif d["status"] == "finished":
                    self.after(0, self._set_status, "Merging streams...")
                    self.after(0, self._set_progress, 0.95)

            opts = {
                "format": fmt,
                "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
                "merge_output_format": "mp4" if not audio_only else None,
                "progress_hooks": [progress_hook],
                "postprocessors": postprocessors,
                "noplaylist": True, "quiet": True, "no_warnings": True,
                "ffmpeg_location": FFMPEG_DIR,
            }
            opts = {k: v for k, v in opts.items() if v is not None}

            start_time = time.time()

            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get("title", "Unknown")
                duration = info.get("duration_string", "?")
                self.after(0, lambda t=title, d=duration: self.title_label.configure(text=f"{t}  ({d})"))

                if self._download_id != my_id:
                    return

                # Get the actual filename yt-dlp will use
                prepared = ydl.prepare_filename(info)
                ext = "mp3" if audio_only else "mp4"
                expected_file = os.path.splitext(prepared)[0] + "." + ext

                self.after(0, self._set_status, "Downloading...")
                ydl.download([url])

            if self._download_id != my_id:
                return

            # Find the downloaded file
            downloaded_file = None
            if os.path.exists(expected_file):
                downloaded_file = expected_file
            else:
                # Fallback: find newest mp4/mp3 in output dir created after we started
                search_ext = "*.mp3" if audio_only else "*.mp4"
                candidates = glob.glob(os.path.join(output_dir, search_ext))
                candidates = [f for f in candidates if os.path.getmtime(f) >= start_time]
                if candidates:
                    downloaded_file = max(candidates, key=os.path.getmtime)

            # Re-encode to H.264 for Premiere Pro compatibility
            if not audio_only and downloaded_file and downloaded_file.endswith(".mp4"):
                codec = self._get_video_codec(downloaded_file)
                if codec and codec != "h264":
                    self.after(0, self._set_status, f"Re-encoding to H.264 (was {codec})...")
                    self.after(0, self._set_progress, 0.5)
                    self._reencode_to_h264(downloaded_file)

            if self._download_id != my_id:
                return

            self._last_downloaded_file = downloaded_file
            self.after(0, self._set_progress, 1.0)
            self.after(0, self._set_status, f"Done! Saved to {output_dir}")
        except Exception as e:
            if self._download_id == my_id and not self._cancelled:
                self.after(0, self._set_status, f"Error: {e}")
                self.after(0, self._set_progress, 0)
        finally:
            if self._download_id == my_id:
                self._downloading = False
                self.after(0, lambda: self.dl_button.configure(state="normal", text="Download"))
                self.after(0, lambda: self.cancel_button.configure(state="disabled"))

    @staticmethod
    def _get_video_codec(filepath):
        cmd = [os.path.join(FFMPEG_DIR, "ffprobe"), "-v", "quiet", "-select_streams", "v:0",
               "-show_entries", "stream=codec_name", "-of", "csv=p=0", filepath]
        return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()

    @staticmethod
    def _reencode_to_h264(filepath):
        tmp_path = filepath + ".tmp.mp4"
        cmd = [os.path.join(FFMPEG_DIR, "ffmpeg"), "-y", "-i", filepath, "-c:v", "libx264", "-preset", "medium",
               "-crf", "18", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart",
               "-pix_fmt", "yuv420p", tmp_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            os.replace(tmp_path, filepath)
        elif os.path.exists(tmp_path):
            os.remove(tmp_path)


if __name__ == "__main__":
    _app = App()
    _app.mainloop()
