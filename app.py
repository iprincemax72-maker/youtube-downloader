#!/usr/bin/env python3
"""YouTube Downloader — unified menu bar + GUI app."""

import os
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog

import certifi

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

# Ensure ffmpeg is findable (Homebrew paths not in bundled app's PATH)
for p in ["/opt/homebrew/bin", "/usr/local/bin"]:
    if p not in os.environ.get("PATH", ""):
        os.environ["PATH"] = p + ":" + os.environ.get("PATH", "")

import customtkinter as ctk
import yt_dlp

DOWNLOAD_DIR = os.path.expanduser("~/Downloads")
FFMPEG_DIR = "/opt/homebrew/bin"

QUALITY_MAP = {
    "Best":   "bestvideo+bestaudio/best",
    "4K":     "bestvideo[height<=2160]+bestaudio/best[height<=2160]",
    "1440p":  "bestvideo[height<=1440]+bestaudio/best[height<=1440]",
    "1080p":  "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "720p":   "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "480p":   "bestvideo[height<=480]+bestaudio/best[height<=480]",
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
        self._dl_proc = None
        self._build_ui()

        # Set up menu bar icon after tkinter is initialized
        self._has_menubar = setup_menubar()
        if self._has_menubar:
            self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        self.withdraw()

    def _build_ui(self):
        pad = {"padx": 20, "pady": (8, 0)}

        ctk.CTkLabel(self, text="YouTube URL", anchor="w").pack(fill="x", **pad)
        self.url_entry = ctk.CTkEntry(self, placeholder_text="https://www.youtube.com/watch?v=...")
        self.url_entry.pack(fill="x", padx=20, pady=(4, 0))

        ctk.CTkLabel(self, text="Quality", anchor="w").pack(fill="x", **pad)
        self.quality_var = ctk.StringVar(value="Best")
        self.quality_menu = ctk.CTkOptionMenu(
            self, variable=self.quality_var, values=list(QUALITY_MAP.keys()), width=200)
        self.quality_menu.pack(anchor="w", padx=20, pady=(4, 0))

        toggle_frame = ctk.CTkFrame(self, fg_color="transparent")
        toggle_frame.pack(fill="x", padx=20, pady=(14, 0))

        self.premiere_var = ctk.BooleanVar(value=False)
        self.premiere_switch = ctk.CTkSwitch(toggle_frame, text="Premiere Pro compatible",
                                              variable=self.premiere_var)
        self.premiere_switch.pack(side="left", padx=(0, 30))

        self.audio_var = ctk.BooleanVar(value=False)
        self.audio_switch = ctk.CTkSwitch(toggle_frame, text="Audio only (MP3 320kbps)",
                                           variable=self.audio_var, command=self._on_audio_toggle)
        self.audio_switch.pack(side="left")

        ctk.CTkLabel(self, text="Output Folder", anchor="w").pack(fill="x", **pad)
        folder_frame = ctk.CTkFrame(self, fg_color="transparent")
        folder_frame.pack(fill="x", padx=20, pady=(4, 0))

        self.folder_var = ctk.StringVar(value=DOWNLOAD_DIR)
        self.folder_entry = ctk.CTkEntry(folder_frame, textvariable=self.folder_var)
        self.folder_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(folder_frame, text="Browse", width=80, command=self._browse).pack(side="left")

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(20, 0))

        self.dl_button = ctk.CTkButton(
            btn_frame, text="Download", height=42, font=ctk.CTkFont(size=15, weight="bold"),
            command=self._start_download)
        self.dl_button.pack(side="left", fill="x", expand=True, padx=(0, 5))

        self.cancel_button = ctk.CTkButton(
            btn_frame, text="Cancel", width=100, height=42, font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#cc0000", hover_color="#990000", state="disabled",
            command=self._cancel_download)
        self.cancel_button.pack(side="left", padx=(5, 5))

        self.again_button = ctk.CTkButton(
            btn_frame, text="New", width=80, height=42, font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#2d8a4e", hover_color="#1e6b3a",
            command=self._reset)
        self.again_button.pack(side="left")

        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.pack(fill="x", padx=20, pady=(16, 0))
        self.progress_bar.set(0)

        self.status_label = ctk.CTkLabel(self, text="Ready", anchor="w",
                                          font=ctk.CTkFont(size=12), text_color="gray")
        self.status_label.pack(fill="x", padx=20, pady=(6, 0))

        self.title_label = ctk.CTkLabel(self, text="", anchor="w", wraplength=560,
                                         font=ctk.CTkFont(size=12))
        self.title_label.pack(fill="x", padx=20, pady=(4, 10))

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

    def _reset(self):
        if self._downloading:
            return
        self.url_entry.delete(0, "end")
        self._set_progress(0)
        self._set_status("Ready")
        self.title_label.configure(text="")
        self.url_entry.focus()

    def _cancel_download(self):
        self._cancelled = True
        if self._dl_proc and self._dl_proc.poll() is None:
            os.killpg(os.getpgid(self._dl_proc.pid), 9)
        self._downloading = False
        self._dl_proc = None
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
        self._dl_proc = None
        self.dl_button.configure(state="disabled", text="Downloading...")
        self.cancel_button.configure(state="normal")
        self._set_progress(0)
        self._set_status("Fetching video info...")
        self.title_label.configure(text="")
        threading.Thread(target=self._download_thread, args=(url,), daemon=True).start()

    def _download_thread(self, url):
        import json, re, signal
        try:
            output_dir = self.folder_var.get()
            audio_only = self.audio_var.get()
            premiere = self.premiere_var.get()
            quality = self.quality_var.get()

            # Get video info first (fast, in-process)
            opts = {"quiet": True, "no_warnings": True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get("title", "Unknown")
                duration = info.get("duration_string", "?")
                self.after(0, self.title_label.configure, {"text": f"{title}  ({duration})"})

            if self._cancelled:
                return

            # Build yt-dlp command
            if audio_only:
                fmt = "bestaudio/best"
            else:
                fmt = QUALITY_MAP.get(quality, QUALITY_MAP["Best"])

            cmd = [
                "/Library/Frameworks/Python.framework/Versions/3.14/bin/yt-dlp",
                "-f", fmt,
                "-o", os.path.join(output_dir, "%(title)s.%(ext)s"),
                "--newline",
                "--no-playlist",
                "--ffmpeg-location", FFMPEG_DIR,
            ]
            if not audio_only:
                cmd += ["--merge-output-format", "mp4"]
            if audio_only:
                cmd += ["-x", "--audio-format", "mp3", "--audio-quality", "320K"]
            cmd.append(url)

            self.after(0, self._set_status, "Downloading...")
            self._dl_proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, preexec_fn=os.setsid)

            # Parse progress from yt-dlp output
            for line in self._dl_proc.stdout:
                line = line.strip()
                m = re.search(r'(\d+\.?\d*)%', line)
                if m:
                    pct = float(m.group(1)) / 100.0
                    self.after(0, self._set_progress, pct)
                if "ETA" in line or "%" in line:
                    self.after(0, self._set_status, line[:80])
                elif "Merging" in line or "merger" in line.lower():
                    self.after(0, self._set_status, "Merging streams...")
                    self.after(0, self._set_progress, 0.95)

            self._dl_proc.wait()

            if self._cancelled:
                return

            if self._dl_proc.returncode != 0:
                self.after(0, self._set_status, "Download failed.")
                self.after(0, self._set_progress, 0)
                return

            # Premiere Pro re-encode if needed
            if not audio_only and premiere:
                # Find the output file
                safe_title = title.replace("/", "_")
                mp4_path = os.path.join(output_dir, safe_title + ".mp4")
                if os.path.exists(mp4_path):
                    codec = self._get_video_codec(mp4_path)
                    if codec and codec != "h264":
                        self.after(0, self._set_status, f"Re-encoding to H.264 (was {codec})...")
                        self.after(0, self._set_progress, 0.5)
                        self._reencode_to_h264(mp4_path)

            self.after(0, self._set_progress, 1.0)
            self.after(0, self._set_status, f"Done! Saved to {output_dir}")
        except Exception as e:
            if not self._cancelled:
                self.after(0, self._set_status, f"Error: {e}")
                self.after(0, self._set_progress, 0)
        finally:
            self._downloading = False
            self._cancelled = False
            self._dl_proc = None
            self.after(0, self.dl_button.configure, {"state": "normal", "text": "Download"})
            self.after(0, self.cancel_button.configure, {"state": "disabled"})

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
