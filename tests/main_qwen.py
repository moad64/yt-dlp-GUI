"""
yt-dlp GUI - A modern YouTube downloader with CustomTkinter interface
Fixed version with improved error handling, security, and cross-platform support
"""

import customtkinter as ctk
import yt_dlp
import requests
from PIL import Image
import os
import subprocess
import re
import json
import threading
import tkinter.messagebox as msgbox
from tkinter import filedialog
import shutil
from concurrent.futures import ThreadPoolExecutor
import time
import sys
import tempfile
from pathlib import Path

# Cross-platform folder setup
def get_main_folder():
    """Get the main application folder in a cross-platform way."""
    if sys.platform == "win32":
        base = os.environ.get('APPDATA', str(Path.home()))
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = str(Path.home())
    
    main_folder = os.path.join(base, ".yt-dlp-GUI")
    return main_folder

main_folder = get_main_folder()

# Create necessary directories
for subdir in ["thumb", "download"]:
    path = os.path.join(main_folder, subdir)
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)

data_file_path = os.path.join(main_folder, "data.json")
settings_config_file_path = os.path.join(main_folder, "settings.json")

# Load data with proper error handling
try:
    with open(data_file_path, "r") as f:
        data = json.load(f)
        results = data.get("results", {})
        playlist_title = data.get("playlist_title")
except Exception as e:
    print(f"Error loading data: {e}")
    data = {}
    results = {}
    playlist_title = None

# Load settings with defaults
try:
    with open(settings_config_file_path, "r") as f:
        settings_config = json.load(f)
except Exception:
    settings_config = {
        "ui": {
            "main_color": "blue",
            "second_color": "black"
        },
        "search": {
            "results_number": 9,
            "thumbnail_quality": 0
        }
    }

ctk.set_appearance_mode("dark")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.results = results
        self.playlist_title = playlist_title
        self.download_functionality = True
        self.loading_animation = False
        self.common_formats = {}
        
        self.title("yt-dlp GUI")
        self.geometry("720x465")
        self.resizable(False, False)
        self.configure(bg="black")

        # Title frame
        title_frame = ctk.CTkFrame(self)
        title_frame.pack(padx=5, pady=5, side="top", fill="x")
        title_frame.bind("<Button-1>", self.settings)
        label = ctk.CTkLabel(
            title_frame, 
            text="Welcome to yt-dlp GUI!", 
            font=("Classic Console", 50), 
            text_color=settings_config["ui"]["main_color"]
        )
        label.pack(pady=20)
        
        # Search frame
        search_frame = ctk.CTkFrame(self)
        search_frame.pack(padx=5, pady=5, fill="x")
        self.search = ctk.CTkEntry(
            search_frame, 
            placeholder_text="Enter URL or search term"
        )
        self.search.bind("<KP_Enter>", self.on_press)
        self.search.bind("<Return>", self.on_press)
        self.search.focus_set()
        self.search.pack(side="left", padx=10, pady=10, fill="x", expand=True)

        search_button = ctk.CTkButton(
            search_frame, 
            text="Search", 
            command=self.search_yt, 
            fg_color=settings_config["ui"]["main_color"],
            hover_color=settings_config["ui"]["second_color"]
        )
        search_button.pack(side="right", pady=10, padx=10)

        # Results frame
        self.results_frame = ctk.CTkScrollableFrame(self)
        self.results_frame.pack(padx=5, pady=5, fill="both", expand=True)
        
        if self.results:
            self.resultsshow()
        
        # Bind mousewheel for Linux
        self.results_frame._parent_canvas.bind("<Enter>", self._bind_mousewheel_linux)
        self.results_frame._parent_canvas.bind("<Leave>", self._unbind_mousewheel_linux)

        # Check for ffmpeg
        if shutil.which("ffmpeg") is None:
            self.error("FFmpeg is not installed!\nPlease install it to enable downloading functionality")
            self.download_functionality = False

    def save(self):
        """Save current state to data file."""
        try:
            data["results"] = self.results
            data["playlist_title"] = self.playlist_title
            with open(data_file_path, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error saving data: {e}")

    def _bind_mousewheel_linux(self, event):
        """Bind mousewheel events for Linux."""
        self.results_frame._parent_canvas.bind_all("<Button-4>", self._on_mousewheel_linux)
        self.results_frame._parent_canvas.bind_all("<Button-5>", self._on_mousewheel_linux)

    def _unbind_mousewheel_linux(self, event):
        """Unbind mousewheel events for Linux."""
        self.results_frame._parent_canvas.unbind_all("<Button-4>")
        self.results_frame._parent_canvas.unbind_all("<Button-5>")

    def _on_mousewheel_linux(self, event):
        """Handle mousewheel scrolling for Linux."""
        direction = -1 if event.num == 4 else 1
        self.results_frame._parent_canvas.yview_scroll(direction, "units")

    def truncate_title(self, title, max_length=75):
        """Truncate title to specified length."""
        if len(title) > max_length:
            return title[:max_length] + "..."
        return title

    def on_press(self, event=None):
        """Handle Enter key press."""
        print("Enter key pressed!")
        self.search_yt()

    def clean_cache(self):
        """Clean unused thumbnail cache."""
        try:
            used_thumbs = {thumb["thumb_path"] for thumb in self.results.values()}
            directory = os.path.join(main_folder, "thumb")
            for filename in os.listdir(directory):
                file_path = os.path.join(directory, filename)
                if file_path not in used_thumbs:
                    os.unlink(file_path)
        except Exception as e:
            print(f"Error cleaning cache: {e}")

    def destroy_widgets(self):
        """Destroy all result widgets."""
        for widget in self.results_frame.winfo_children():
            widget.destroy()
        if hasattr(self, 'pl_card_frame') and self.pl_card_frame.winfo_exists():
            self.pl_card_frame.destroy()

    def fetching_playlist_downloads(self):
        """Fetch format information for all videos in playlist."""
        lock = threading.Lock()
        all_formats = {}
        errors = []

        def fetch_video_formats(url, index):
            """Fetch available formats for a single video."""
            try:
                ydl_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'extract_flat': False,
                    'skip_download': True,
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    formats = info.get('formats', [])
                    
                    with lock:
                        all_formats[index] = {
                            'url': url,
                            'title': info.get('title', f'Video {index}'),
                            'formats': formats,
                            'success': True
                        }
                        print(f"✓ Fetched formats for: {info.get('title', 'Unknown')[:50]}")
                        
            except Exception as e:
                with lock:
                    errors.append({
                        'url': url,
                        'error': str(e),
                        'index': index
                    })
                    print(f"✗ Error fetching {url}: {e}")

        threads = []
        print(f"Starting to fetch formats for {len(self.results)} videos...")

        for i, result in enumerate(self.results.values()):
            if 'url' in result:
                thread = threading.Thread(
                    target=fetch_video_formats,
                    args=(result['url'], i),
                    daemon=True
                )
                threads.append(thread)
                thread.start()

        for thread in threads:
            thread.join()

        print(f"\nFetching complete. Success: {len(all_formats)}, Errors: {len(errors)}")

        if all_formats:
            videos_with_formats = [d for d in all_formats.values() if d['success']]
            
            if not videos_with_formats:
                print("No videos have format information.")
                return

            first_video = videos_with_formats[0]
            all_video_formats = first_video['formats']

            common_v_extensions = set()
            common_resolutions = set()
            common_v_codecs = set()
            common_fpss = set()
            common_protocols = set()
            common_a_qualities = set()
            common_a_extensions = set()

            def extract_format_properties(format_list):
                v_exts = set()
                res = set()
                v_codes = set()
                fps_set = set()
                protos = set()
                a_quals = set()
                a_exts = set()

                for fmt in format_list:
                    if fmt.get('vcodec') != 'none':
                        if fmt.get('ext'):
                            v_exts.add(fmt['ext'])
                        if fmt.get('height'):
                            resolution = f"{fmt.get('width', '?')}x{fmt['height']}"
                            res.add(resolution)
                        if fmt.get('vcodec') and fmt['vcodec'] != 'none':
                            codec = fmt['vcodec'].split('.')[0]
                            if codec and codec != 'none':
                                v_codes.add(codec)
                        if fmt.get('fps'):
                            fps_set.add(str(fmt['fps']))

                    if fmt.get('acodec') != 'none':
                        if fmt.get('asr'):
                            a_quals.add(str(fmt['asr']))
                        if fmt.get('acodec') and fmt['acodec'] != 'none':
                            acodec = fmt['acodec'].split('.')[0]
                            if acodec:
                                a_exts.add(acodec)

                    if fmt.get('protocol'):
                        protos.add(fmt['protocol'])

                return v_exts, res, v_codes, fps_set, protos, a_quals, a_exts

            (common_v_extensions, common_resolutions, common_v_codecs, 
             common_fpss, common_protocols, common_a_qualities, 
             common_a_extensions) = extract_format_properties(all_video_formats)

            for video_data in videos_with_formats[1:]:
                formats = video_data['formats']
                (v_exts, res, v_codes, fps_set, protos, a_quals, a_exts) = extract_format_properties(formats)
                
                common_v_extensions &= v_exts
                common_resolutions &= res
                common_v_codecs &= v_codes
                common_fpss &= fps_set
                common_protocols &= protos
                common_a_qualities &= a_quals
                common_a_extensions &= a_exts

            v_extensions = sorted(common_v_extensions)
            resolutions = sorted(common_resolutions, 
                               key=lambda x: (int(x.split('x')[1]) if 'x' in x else 0, x))
            v_codecs = sorted(common_v_codecs)
            fpss = sorted(common_fpss, 
                         key=lambda x: float(x) if x.replace('.', '').isdigit() else 0)
            protocols = sorted(common_protocols)
            a_qualities = sorted(common_a_qualities, 
                               key=lambda x: int(x) if x.isdigit() else 0)
            a_extensions = sorted(common_a_extensions)

            print("\n" + "="*50)
            print("COMMON FORMATS ACROSS ALL VIDEOS:")
            print("="*50)
            print(f"Video Extensions: {v_extensions}")
            print(f"Resolutions: {resolutions}")
            print(f"Video Codecs: {v_codecs}")
            print(f"FPS Values: {fpss}")
            print(f"Protocols: {protocols}")
            print(f"Audio Qualities (Hz): {a_qualities}")
            print(f"Audio Extensions: {a_extensions}")

            self.common_formats = {
                'v_extensions': v_extensions,
                'resolutions': resolutions,
                'v_codecs': v_codecs,
                'fpss': fpss,
                'protocols': protocols,
                'a_qualities': a_qualities,
                'a_extensions': a_extensions
            }
            self.after(0, lambda: self.options_show(None))

    def resultsshow(self):
        """Display search results."""
        self.destroy_widgets()
        for idx, result in enumerate(self.results.values()):
            row = idx // 3
            col = idx % 3
            result_frame = ctk.CTkFrame(
                self.results_frame, 
                fg_color="#424042", 
                border_color=settings_config["ui"]["second_color"], 
                border_width=2, 
                height=250
            )
            result_frame.grid(row=row, column=col, padx=5, pady=5, sticky="n")
            result_frame.grid_propagate(False)

            ctk_image = None
            if os.path.exists(result["thumb_path"]):
                try:
                    img = Image.open(result["thumb_path"])
                    img = img.resize((200, 100))
                    ctk_image = ctk.CTkImage(img, size=(200, 100))
                except Exception as e:
                    print(f"Error loading thumbnail: {e}")

            thumbnail_label = ctk.CTkLabel(result_frame, image=ctk_image, text="")
            thumbnail_label.pack(pady=6, padx=10)
            
            video_title = ctk.CTkLabel(
                result_frame, 
                text=self.truncate_title(str(result["title"])), 
                font=("Arial", 15), 
                wraplength=200, 
                height=75
            )
            video_title.pack(pady=0, padx=10, fill="both", expand=True)
            
            download_btn = ctk.CTkButton(
                result_frame, 
                text="download or watch", 
                fg_color=settings_config["ui"]["main_color"], 
                hover_color=settings_config["ui"]["second_color"], 
                command=lambda current=result: self.download_window(current)
            )
            download_btn.pack(pady=(0, 6), padx=5, fill="x", side="bottom")

        if self.playlist_title:
            self.pl_card_frame = ctk.CTkFrame(
                self, 
                fg_color=settings_config["ui"]["main_color"]
            )
            self.pl_card_frame.pack(padx=5, pady=(0, 5), fill="both")
            pl_title_label = ctk.CTkLabel(
                self.pl_card_frame, 
                text=self.playlist_title, 
                font=("Arial", 20, "bold")
            )
            pl_title_label.pack(padx=10, pady=5, side="left")
            
            p_label = ctk.CTkLabel(
                self.pl_card_frame, 
                text="- playlist", 
                font=("Arial", 15)
            )
            p_label.pack(padx=0, pady=5, side="left")

    def animate_loading(self, label, count=0):
        """Animate loading dots."""
        if not self.loading_animation:
            return
        dots = '.' * (count % 4)
        label.configure(text=f"Loading{dots}")
        self.after(500, lambda: self.animate_loading(label, count + 1))

    def download_window(self, result):
        """Open download options window."""
        self.dw = ctk.CTkToplevel(self)
        self.dw.geometry("300x700")
        self.dw.title("Download")
        self.dw.resizable(False, False)
        
        title_frame = ctk.CTkFrame(self.dw)
        title_frame.pack(padx=5, pady=5, fill="x")

        if not self.download_functionality:
            ndf = ctk.CTkLabel(
                self.dw, 
                text="NO DOWNLOAD FUNCTIONALITY!\nPlease install ffmpeg"
            )
            ndf.place(relx=0.5, rely=0.5, anchor="center")
            return

        if result:
            title_text = self.truncate_title(str(result.get("title", "Unknown")), 75)
            title = ctk.CTkLabel(
                title_frame, 
                text=f"{title_text} ...", 
                font=('Arial', 15), 
                wraplength=250
            )
            title.pack(padx=5, pady=5)
            
            thumb_frame = ctk.CTkFrame(title_frame)
            thumb_frame.pack(padx=10, pady=(0, 10), expand=True, fill="both")
            
            ctk_image = None
            if os.path.exists(result.get("thumb_path", "")):
                try:
                    img = Image.open(result["thumb_path"])
                    img = img.resize((250, 125))
                    ctk_image = ctk.CTkImage(img, size=(250, 125))
                except Exception as e:
                    print(f"Error loading thumbnail: {e}")
            
            self.thumbnail_label = ctk.CTkLabel(
                thumb_frame, 
                image=ctk_image, 
                text="", 
                font=('Arial', 50), 
                text_color=settings_config["ui"]["second_color"]
            )
            self.thumbnail_label.pack(pady=10, padx=10)
            
            self.options_frame = ctk.CTkFrame(self.dw)
            self.options_frame.pack(padx=5, pady=(0, 5), expand=True, fill="both")

            if (result.get("audios") and result.get("videos")) and self.download_functionality:
                self.loading_animation = False
                self.thumbnail_label.configure(
                    text="▶️", 
                    font=('Arial', 50), 
                    text_color=settings_config["ui"]["second_color"]
                )
                self.thumbnail_label.bind(
                    "<Button-1>", 
                    lambda e, url=result["url"]: self.open_in_vlc(url)
                )
                self.options_show(result)
            elif (not result.get("audios") and not result.get("videos")) and self.download_functionality:
                self.thumbnail_label.configure(text="loading...", font=('Arial', 15))
                self.loading = ctk.CTkLabel(self.options_frame, text="loading...")
                self.loading.place(relx=0.5, rely=0.5, anchor="center")
                self.loading_animation = True
                self.animate_loading(self.loading)
                threading.Thread(
                    target=self.fetching_downloads, 
                    args=(result,)
                ).start()
        else:
            title = ctk.CTkLabel(
                title_frame, 
                text=self.playlist_title or "Playlist", 
                font=('Arial', 15), 
                wraplength=250
            )
            title.pack(padx=5, pady=5)
            
            self.options_frame = ctk.CTkFrame(self.dw)
            self.options_frame.pack(padx=5, pady=(0, 5), expand=True, fill="both")

            if (self.results.get("audios") and self.results.get("videos")) and self.download_functionality:
                self.loading_animation = False
                self.options_show(result=None)
            elif (not self.results.get("audios") and not self.results.get("videos")) and self.download_functionality:
                self.loading = ctk.CTkLabel(
                    self.options_frame, 
                    text="loading playlist ..."
                )
                self.loading.place(relx=0.5, rely=0.5, anchor="center")
                self.loading_animation = True
                self.animate_loading(self.loading)
                threading.Thread(target=self.fetching_playlist_downloads).start()

    def open_in_vlc(self, url):
        """Open URL in VLC player (cross-platform)."""
        try:
            # Try to kill existing VLC instances gracefully
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/IM", "vlc.exe"], 
                             stdout=subprocess.DEVNULL, 
                             stderr=subprocess.DEVNULL)
            else:
                subprocess.run(["pkill", "vlc"], 
                             stdout=subprocess.DEVNULL, 
                             stderr=subprocess.DEVNULL)
            
            subprocess.Popen(["vlc", url])
        except Exception as e:
            self.error(f"Failed to open VLC: {e}")

    def fetching_downloads(self, result, jfs=False):
        """Fetch download formats for a single video."""
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'format': 'best',
            'extractor_args': {
                'youtube': {
                    'player_client': ['android_vr'],
                    'player_skip': ['configs'],
                }
            }
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(result["url"], download=False)
        except Exception as e:
            self.error(f"Error: {e}")
            self.failed = True
            return
        
        result["rfs"] = info.get("url", "")
        formats = info.get("formats", [])
        video_formats = [f for f in formats 
                        if f.get("vcodec") != "none" and f.get("acodec") == "none"]
        audio_formats = [f for f in formats 
                        if f.get("acodec") != "none" and f.get("vcodec") == "none"]
        
        result["videos"] = {}
        for i, vid in enumerate(video_formats):
            result["videos"][f"video{i}"] = {
                "resolution": vid.get("height", 0),
                "url": vid.get("url", ""),
                "protocol": vid.get("protocol", ""),
                "fps": vid.get("fps", 0),
                "extension": vid.get("ext", "mp4"),
                "codec": vid.get("vcodec", "")
            }
        
        result["audios"] = {}
        for i, aud in enumerate(audio_formats):
            result["audios"][f"audio{i}"] = {
                "quality": aud.get("format_note", ""),
                "extension": aud.get("audio_ext", "m4a"),
                "url": aud.get("url", ""),
                "protocol": aud.get("protocol", "")
            }
        
        self.save()
        self.loading_animation = False
        
        if self.thumbnail_label:
            self.thumbnail_label.configure(
                text="▶️", 
                font=('Arial', 50), 
                text_color=settings_config["ui"]["second_color"]
            )
            self.thumbnail_label.bind(
                "<Button-1>", 
                lambda e, url=result.get("rfs", ""): self.open_in_vlc(url)
            )
        
        if not jfs:
            self.after(0, lambda: self.options_show(result))

    def options_show(self, result):
        """Show download options."""
        v_extensions = []
        resolutions = []
        v_codecs = []
        fpss = []
        protocols = []
        a_qualities = []
        a_extensions = []

        if result:
            for vid in result.get("videos", {}).values():
                v_extensions.append(vid.get("extension", ""))
                v_codecs.append(vid.get("codec", "")[:4])
                resolutions.append(f"{vid.get('resolution', 0)}p")
                fpss.append(vid.get("fps", 0))
                protocols.append(vid.get("protocol", ""))
            
            for aud in result.get("audios", {}).values():
                a_extensions.append(aud.get("extension", ""))
                a_qualities.append(aud.get("quality", ""))

        if hasattr(self, "loading"):
            self.loading.destroy()
        
        vora_frame = ctk.CTkFrame(self.options_frame)
        vora_frame.pack(padx=5, pady=(5, 0), fill="both")
        
        video_label = ctk.CTkLabel(vora_frame, text="video")
        video_label.pack(padx=20, pady=5, side="left")
        
        self.v_check = ctk.CTkCheckBox(vora_frame, text="")
        self.v_check.pack(padx=0, pady=5, side="right")
        
        video_options_frame = ctk.CTkFrame(self.options_frame)
        video_options_frame.pack(padx=5, pady=5, fill="both")

        # Extension option
        de_frame = ctk.CTkFrame(video_options_frame)
        de_frame.pack(padx=5, pady=(5, 0), fill="both")
        labelone_e = ctk.CTkLabel(de_frame, text="extension :")
        labelone_e.pack(padx=20, pady=(0, 0), fill="both", side="left")
        
        ext_values = list(set(v_extensions)) if v_extensions else ["mp4"]
        self.extension_option = ctk.CTkOptionMenu(
            de_frame, 
            values=[str(r) for r in ext_values]
        )
        self.extension_option.set(ext_values[0] if ext_values else "mp4")
        self.extension_option.pack(pady=5, padx=5, side="right")

        # Codec option
        dc_frame = ctk.CTkFrame(video_options_frame)
        dc_frame.pack(padx=5, pady=(5, 0), fill="both")
        labelvc = ctk.CTkLabel(dc_frame, text="codec :")
        labelvc.pack(padx=20, pady=(0, 0), fill="both", side="left")
        
        codec_values = list(set(v_codecs)) if v_codecs else ["avc1"]
        self.codec_option = ctk.CTkOptionMenu(
            dc_frame, 
            values=[str(r) for r in codec_values]
        )
        self.codec_option.set(codec_values[0] if codec_values else "avc1")
        self.codec_option.pack(pady=5, padx=5, side="right")

        # Quality option
        dq_frame = ctk.CTkFrame(video_options_frame)
        dq_frame.pack(padx=5, pady=(5, 5), fill="both")
        labelone = ctk.CTkLabel(dq_frame, text="quality :")
        labelone.pack(padx=20, pady=(0, 0), fill="both", side="left")
        
        quality_values = list(set(resolutions)) if resolutions else ["720p"]
        self.quality_option = ctk.CTkOptionMenu(
            dq_frame, 
            values=[str(r) for r in quality_values]
        )
        self.quality_option.set(quality_values[0] if quality_values else "720p")
        self.quality_option.pack(pady=5, padx=5, side="right")

        # FPS option
        df_frame = ctk.CTkFrame(video_options_frame)
        df_frame.pack(padx=5, pady=(0, 5), fill="both")
        labeltwo = ctk.CTkLabel(df_frame, text="frame_rate :")
        labeltwo.pack(padx=20, pady=(0, 0), fill="both", side="left")
        
        fps_values = list(set([int(f) for f in fpss if f])) if fpss else [30]
        self.fps_option = ctk.CTkOptionMenu(
            df_frame, 
            values=[str(int(r)) for r in fps_values]
        )
        self.fps_option.set(str(fps_values[0]) if fps_values else "30")
        self.fps_option.pack(pady=5, padx=5, side="right")

        # Protocol option
        dp_frame = ctk.CTkFrame(video_options_frame)
        dp_frame.pack(padx=5, pady=(0, 5), fill="both")
        labelthree = ctk.CTkLabel(dp_frame, text="protocol :")
        labelthree.pack(padx=20, pady=(0, 0), fill="both", side="left")
        
        proto_values = list(set(protocols)) if protocols else ["https"]
        self.prtc_option = ctk.CTkOptionMenu(
            dp_frame, 
            values=proto_values
        )
        self.prtc_option.set(proto_values[0] if proto_values else "https")
        self.prtc_option.pack(pady=5, padx=5, side="right")

        # Audio options
        a_options_frame = ctk.CTkFrame(self.dw)
        a_options_frame.pack(padx=5, pady=(0, 5), fill="both")
        
        vora_frame2 = ctk.CTkFrame(a_options_frame)
        vora_frame2.pack(padx=5, pady=5, fill="both")
        
        audio_label = ctk.CTkLabel(vora_frame2, text="audio")
        audio_label.pack(padx=20, pady=5, side="left")
        
        self.a_check = ctk.CTkCheckBox(vora_frame2, text="")
        self.a_check.pack(padx=0, pady=5, side="right")
        
        sub_a_options_frame = ctk.CTkFrame(a_options_frame)
        sub_a_options_frame.pack(padx=5, pady=(0, 5), fill="both")
        
        dae_frame = ctk.CTkFrame(sub_a_options_frame)
        dae_frame.pack(padx=5, pady=(5, 5), fill="both")
        labelae = ctk.CTkLabel(dae_frame, text="extension :")
        labelae.pack(padx=20, pady=(0, 0), fill="both", side="left")
        
        a_ext_values = list(set(a_extensions)) if a_extensions else ["m4a"]
        self.a_extension_option = ctk.CTkOptionMenu(
            dae_frame, 
            values=[str(r) for r in a_ext_values]
        )
        self.a_extension_option.set(a_ext_values[0] if a_ext_values else "m4a")
        self.a_extension_option.pack(pady=5, padx=5, side="right")
        
        daq_frame = ctk.CTkFrame(sub_a_options_frame)
        daq_frame.pack(padx=5, pady=(0, 5), fill="both")
        labelaq = ctk.CTkLabel(daq_frame, text="audio quality :")
        labelaq.pack(padx=20, pady=(0, 0), fill="both", side="left")
        
        a_qual_values = list(set(a_qualities)) if a_qualities else ["medium"]
        self.a_quality_option = ctk.CTkOptionMenu(
            daq_frame, 
            values=[str(r) for r in a_qual_values]
        )
        self.a_quality_option.set(a_qual_values[0] if a_qual_values else "medium")
        self.a_quality_option.pack(pady=5, padx=5, side="right")
        
        if not self.playlist_title:
            check = ctk.CTkButton(
                self.dw, 
                text="download", 
                command=lambda current=result: self.getting_download(current)
            )
        else:
            check = ctk.CTkButton(
                self.dw, 
                text="download", 
                command=self.download_playlist
            )
        check.pack(padx=5, pady=5)

    def getting_download(self, result):
        """Process download based on selected options."""
        if hasattr(self, 'error_window') and self.error_window.winfo_exists():
            self.error_window.destroy()
        
        if self.v_check.get() and not self.a_check.get():
            found = False
            for key, vid in result.get("videos", {}).items():
                if (vid.get("codec", "")[:4] == self.codec_option.get() and
                    str(vid.get("resolution", 0)) == self.quality_option.get().removesuffix("p") and
                    vid.get("extension", "") == self.extension_option.get() and
                    vid.get("fps", 0) == int(self.fps_option.get()) and
                    vid.get("protocol", "") == self.prtc_option.get()):
                    found = True
                    title = self.sanitize_filename(result.get("title", "video"))
                    self.start_downloading(
                        vid.get("url", ""), 
                        vid.get("extension", "mp4"), 
                        f"{title}_VIDEO"
                    )
                    break
            
            if not found:
                self.error("No video was found, try another combination 🙂")
                return
                
        elif self.a_check.get() and not self.v_check.get():
            found = False
            for key, aud in result.get("audios", {}).items():
                if (aud.get("quality", "") == self.a_quality_option.get() and
                    aud.get("extension", "") == self.a_extension_option.get()):
                    found = True
                    title = self.sanitize_filename(result.get("title", "audio"))
                    self.start_downloading(
                        aud.get("url", ""), 
                        aud.get("extension", "m4a"), 
                        f"{title}_AUDIO"
                    )
                    break
            
            if not found:
                self.error("No audio was found, try another combination 🙂")
                return
                
        elif self.v_check.get() and self.a_check.get():
            v_found = False
            v_url = ""
            v_ext = ""
            
            for key, vid in result.get("videos", {}).items():
                if (str(vid.get("resolution", 0)) == self.quality_option.get().removesuffix("p") and
                    vid.get("extension", "") == self.extension_option.get() and
                    vid.get("fps", 0) == int(self.fps_option.get()) and
                    vid.get("protocol", "") == self.prtc_option.get()):
                    v_found = True
                    v_url = vid.get("url", "")
                    v_ext = vid.get("extension", "mp4")
                    break
            
            if not v_found:
                self.error("No video was found, try another combination 🙂")
                return
            
            a_found = False
            a_url = ""
            a_ext = ""
            
            for key, aud in result.get("audios", {}).items():
                if (aud.get("quality", "") == self.a_quality_option.get() and
                    aud.get("extension", "") == self.a_extension_option.get()):
                    a_found = True
                    a_url = aud.get("url", "")
                    a_ext = aud.get("extension", "m4a")
                    break
            
            if not a_found:
                self.error("No audio was found, try another combination 🙂")
                return
            
            if a_found and v_found:
                title = result.get("title", "video")
                video_path = filedialog.asksaveasfilename(
                    initialfile=f"{self.sanitize_filename(title)}_VIDEO.{v_ext}",
                    defaultextension=f".{v_ext}",
                    filetypes=[(f"{v_ext.upper()} files", f"*.{v_ext}"), ("All files", "*.*")],
                    title="Choose where to save video"
                )
                
                if video_path:
                    self.video_folder = os.path.dirname(video_path)
                    self.v_path = video_path
                    self.video_thread = threading.Thread(
                        target=self.saving, 
                        args=(v_url, v_ext, title, video_path, "video")
                    )
                    self.video_thread.start()

                    def wait_and_download_audio():
                        self.video_thread.join()
                        if not os.path.exists(self.v_path):
                            self.error("Video download failed, so audio skipped")
                            return
                        audio_path = os.path.join(
                            self.video_folder, 
                            f"{self.sanitize_filename(title)}_AUDIO.{a_ext}"
                        )
                        self.a_path = audio_path
                        self.audio_thread = threading.Thread(
                            target=self.saving, 
                            args=(a_url, a_ext, title, audio_path, "audio")
                        )
                        self.audio_thread.start()

                    threading.Thread(target=wait_and_download_audio).start()
        else:
            self.error("Please select video and/or audio")

    def error(self, error_msg):
        """Show error dialog."""
        self.error_window = ctk.CTkToplevel(self)
        self.error_window.geometry("300x150")
        self.error_window.title("Error")
        self.error_window.resizable(False, False)

        label = ctk.CTkLabel(
            self.error_window, 
            text=error_msg, 
            text_color="red", 
            font=("Arial", 16), 
            wraplength=250
        )
        label.pack(pady=20)

        ok_button = ctk.CTkButton(
            self.error_window, 
            text="OK", 
            command=self.error_window.destroy
        )
        ok_button.pack(pady=10)

    def start_downloading(self, url, ext, title, type=None):
        """Start download process."""
        save_path = filedialog.asksaveasfilename(
            initialfile=f"{title}.{ext}",
            defaultextension=f".{ext}",
            filetypes=[(f"{ext.upper()} files", f"*.{ext}"), ("All files", "*.*")],
            title="Choose where to save"
        )
        
        if save_path:
            if type == "audio" and hasattr(self, 'video_thread'):
                def wait():
                    self.video_thread.join()
                    audio_thread = threading.Thread(
                        target=self.saving, 
                        args=(url, ext, title, save_path, type)
                    )
                    audio_thread.start()
                
                self.audio_thread = threading.Thread(target=wait)
                self.audio_thread.start()
            else:
                thread = threading.Thread(
                    target=self.saving, 
                    args=(url, ext, title, save_path, type)
                )
                thread.start()

    def saving(self, url, ext, title, save_path, type):
        """Download file using yt-dlp."""
        if not save_path:
            return

        print(f"Downloading to: {save_path}")
        
        aria2c_available = shutil.which("aria2c") is not None

        ydl_opts = {
            'outtmpl': save_path,
            'quiet': True,
            'noplaylist': True,
            'progress': True,
            'continuedl': True,
            'retries': 10,
            'fragment_retries': 10,
            'file_access_retries': 5,
        }

        if aria2c_available:
            ydl_opts.update({
                'external_downloader': 'aria2c',
                'external_downloader_args': [
                    '--max-connection-per-server=16',
                    '--split=16',
                    '--min-split-size=1M',
                    '--max-tries=10',
                    '--retry-wait=2',
                    '--continue=true',
                    '--max-concurrent-downloads=3',
                    '--max-overall-download-limit=0',
                    '--max-download-limit=0',
                    '--optimize-concurrent-downloads=true',
                    '--summary-interval=0',
                    '--auto-file-renaming=false',
                ]
            })
            print("Using aria2c for faster downloads...")
        else:
            print("aria2c not installed, using default downloader")

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            print("Download complete.")

            if type not in ["video", "audio"]:
                folder = os.path.dirname(save_path)
                self.open_folder(folder)

            if type == "video":
                self.v_path = save_path
            elif type == "audio":
                self.a_path = save_path
                self.merging(self.v_path, self.a_path)

        except Exception as e:
            self.error(f"{type} download failed - {e} - try another {type} quality!")
            return

    def open_folder(self, folder):
        """Open folder in file manager (cross-platform)."""
        try:
            if sys.platform == "win32":
                os.startfile(folder)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                # Try common Linux file managers
                for fm in ["thunar", "nautilus", "dolphin", "xdg-open"]:
                    if shutil.which(fm):
                        subprocess.Popen([fm, folder])
                        break
        except Exception as e:
            print(f"Error opening folder: {e}")

    def merging(self, video, audio):
        """Merge video and audio files using ffmpeg."""
        print(f"video: {video}")
        print(f"audio: {audio}")
        output_path = video.replace("_VIDEO", "")
        
        command = [
            "ffmpeg",
            "-loglevel", "error",
            "-i", video,
            "-i", audio,
            "-c:v", "copy",
            "-c:a", "aac",
            "-strict", "experimental",
            output_path
        ]

        try:
            subprocess.run(command, check=True)
            print("Merging complete.")
            
            os.remove(video)
            os.remove(audio)
            self.open_folder(os.path.dirname(output_path))
            
        except subprocess.CalledProcessError as e:
            self.error(f"Merging error: {e}")

    def listing(self, lst):
        """Remove duplicates from list while preserving order."""
        fl = []
        for item in lst:
            if item not in fl:
                fl.append(item)
        return fl

    def sanitize_filename(self, name):
        """Sanitize filename for cross-platform compatibility."""
        title = re.sub(r'[^\w\-_\.\s]', '_', str(name))
        title = title.strip().replace(' ', '_')
        return title[:30]

    def download_playlist(self):
        """Download entire playlist."""
        self.error("Playlist download feature coming soon!")

    def search_yt(self):
        """Search YouTube or process URL."""
        user_input = self.search.get()
        self.playlist_title = None
        self.clean_cache()
        
        self.search_progress = ctk.CTkProgressBar(self, width=200)
        self.search_progress.pack(pady=10)
        self.search_progress.start()
        
        def fetching_video():
            """Fetch single video info."""
            print("started")
            self.failed = False
            self.results = {}
            result = self.results["result"] = {}
            
            ydl_opts = {
                'quiet': True,
                'skip_download': True,
                'format': 'best',
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android_sdkless'],
                        'player_skip': ['configs'],
                    }
                }
            }
            
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(user_input, download=False)
            except Exception as e:
                self.error(f"Error: {e}")
                self.failed = True
                return
            
            result["title"] = info.get("title", "Unknown")
            result["url"] = info.get("url", "")
            
            formats = info.get("formats", [])
            video_formats = [f for f in formats 
                           if f.get("vcodec") != "none" and f.get("acodec") == "none"]
            audio_formats = [f for f in formats 
                           if f.get("acodec") != "none" and f.get("vcodec") == "none"]
            
            result["videos"] = {}
            for i, vid in enumerate(video_formats):
                result["videos"][f"video{i}"] = {
                    "resolution": vid.get("height", 0),
                    "url": vid.get("url", ""),
                    "protocol": vid.get("protocol", ""),
                    "fps": vid.get("fps", 0),
                    "extension": vid.get("ext", "mp4"),
                    "codec": vid.get("vcodec", "")
                }
            
            result["audios"] = {}
            for i, aud in enumerate(audio_formats):
                result["audios"][f"audio{i}"] = {
                    "quality": aud.get("format_note", ""),
                    "extension": aud.get("audio_ext", "m4a"),
                    "url": aud.get("url", ""),
                    "protocol": aud.get("protocol", "")
                }

            thumb_url = None
            if 'thumbnails' in info and info['thumbnails']:
                idx = min(settings_config["search"]["thumbnail_quality"], 
                         len(info['thumbnails']) - 1)
                thumb_url = info['thumbnails'][idx].get('url')
            else:
                thumb_url = info.get('thumbnail')
            
            if thumb_url:
                try:
                    response = requests.get(thumb_url, timeout=10)
                    result["thumb_path"] = os.path.join(
                        main_folder, 
                        "thumb", 
                        f"{self.sanitize_filename(result['title'])}.png"
                    )
                    with open(result["thumb_path"], "wb") as f:
                        f.write(response.content)
                except Exception as e:
                    print(f"Error downloading thumbnail: {e}")
                    result["thumb_path"] = ""
            
            self.search_progress.stop()
            self.search_progress.pack_forget()
            
            if not self.failed:
                self.after(0, lambda: self.download_window(result))
                self.save()

        def fetching_search():
            """Fetch search results."""
            self.playlist_title = None
            self.results = {}
            rn = settings_config["search"]["results_number"]
            self.failed = False
            
            query = f"ytsearch{rn}:{user_input}"
            ydl_opts = {
                'quiet': True,
                'skip_download': True,
                'format': 'best',
                'extract_flat': True,
            }
            
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    start = time.time()
                    info = ydl.extract_info(query, download=False)
                    print("things getted")
            except Exception as e:
                self.error(f"Error: {e}")
                self.failed = True
                return
            
            end = time.time()

            info['entries'] = [
                e for e in info.get('entries', [])
                if e and e.get('ie_key') != 'YoutubeTab'
            ]

            for i in range(len(info["entries"])):
                self.results[f"result{i}"] = {}

            print(f"took {(end - start):.2f}s!")
            
            for entry, result in zip(info["entries"], self.results.values()):
                if not entry:
                    continue
                result["title"] = entry.get("title", "Unknown")
                result["url"] = entry.get("url", "")
                
                thumb_url = None
                if 'thumbnails' in entry and entry['thumbnails']:
                    if settings_config["search"]["thumbnail_quality"] == 0:
                        thumb_url = entry['thumbnails'][0].get('url')
                    else:
                        thumb_url = entry['thumbnails'][-1].get('url')
                else:
                    thumb_url = entry.get('thumbnail')
                
                if thumb_url:
                    try:
                        print(thumb_url)
                        response = requests.get(thumb_url, timeout=10)
                        result["thumb_path"] = os.path.join(
                            main_folder, 
                            "thumb", 
                            f"{self.sanitize_filename(result['title'])}.png"
                        )
                        with open(result["thumb_path"], "wb") as f:
                            f.write(response.content)
                        print("done for an entry")
                    except Exception as e:
                        print(f"Error downloading thumbnail: {e}")
                        result["thumb_path"] = ""
            
            self.after(0, self.search_progress.stop)
            self.after(0, self.search_progress.pack_forget)
            
            if not self.failed:
                self.after(0, self.resultsshow)
                self.after(0, self.save)

        def fetching_playlist():
            """Fetch playlist info."""
            self.results = {}

            class ErrorLogger:
                def __init__(self):
                    self.unavailable = 0

                def error(self, msg):
                    if "Video unavailable" in msg:
                        self.unavailable += 0

                def warning(self, msg):
                    pass

                def debug(self, msg):
                    pass

            logger = ErrorLogger()
            ydl_opts = {
                'quiet': True,
                'skip_download': True,
                'format': 'best',
                'extract_flat': True,
                'ignoreerrors': True,
                'logger': logger
            }
            
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    start = time.time()
                    info = ydl.extract_info(user_input, download=False)
                    missing_videos = logger.unavailable
                    print("things getted")
            except Exception as e:
                print(e)
                self.error(f"Error: {e}")
                self.failed = True
                return
            
            end = time.time()
            self.playlist_title = info.get("title", "Playlist")
            rn = info.get("playlist_count", 0) - missing_videos
            
            for i in range(rn):
                self.results[f"result{i}"] = {}
            
            self.failed = False

            print(f"took {(end - start):.2f}s!")
            
            for entry, result in zip(info.get("entries", []), self.results.values()):
                if not entry:
                    continue
                result["title"] = entry.get("title", "Unknown")
                result["url"] = entry.get("url", "")
                
                thumb_url = None
                if 'thumbnails' in entry and entry['thumbnails']:
                    idx = min(settings_config["search"]["thumbnail_quality"], 
                             len(entry['thumbnails']) - 1)
                    thumb_url = entry['thumbnails'][idx].get('url')
                else:
                    thumb_url = entry.get('thumbnail')

                if thumb_url:
                    try:
                        response = requests.get(thumb_url, timeout=10)
                        result["thumb_path"] = os.path.join(
                            main_folder, 
                            "thumb", 
                            f"{self.sanitize_filename(result['title'])}.png"
                        )
                        with open(result["thumb_path"], "wb") as f:
                            f.write(response.content)
                        print("done for an entry")
                    except Exception as e:
                        print(f"Error downloading thumbnail: {e}")
                        result["thumb_path"] = ""

            self.after(0, self.search_progress.stop)
            self.after(0, self.search_progress.pack_forget)
            
            if not self.failed:
                self.after(0, self.resultsshow)
                self.after(0, self.save)

        if user_input.startswith("https://"):
            if "playlist" in user_input:
                operation = fetching_playlist
            else:
                operation = fetching_video
        else:
            print("search")
            operation = fetching_search
        
        threading.Thread(target=operation).start()

    def settings(self, event):
        """Open settings window."""
        thumbnail_qualities = ["low", "high"]
        
        def save_settings_():
            error = False
            main_color = self.main_color_choice.get()
            second_color = self.second_color_choice.get()
            results_number = self.RESULTS_NUMBER_choice.get()
            thumbnail_quality = self.thumb_quality_option.get()

            def write_to_file():
                with open(settings_config_file_path, "w") as f:
                    json.dump(settings_config, f, indent=4)
                self.destroy()
                os.execl(sys.executable, sys.executable, *sys.argv)

            def is_valid_color(colors):
                try:
                    for color in colors:
                        ImageColor.getcolor(color, "RGB")
                    return True
                except (ValueError, NameError):
                    return False
            
            # Validate colors
            if ((len(main_color) == 7 and main_color.startswith("#")) or 
                is_valid_color([main_color, second_color])):
                settings_config["ui"] = {
                    "main_color": main_color,
                    "second_color": second_color
                }
            else:
                self.main_color_choice.delete(0, "end")
                self.main_color_choice.configure(placeholder_text="wrong choice!")
                self.second_color_choice.delete(0, "end")
                self.second_color_choice.configure(placeholder_text="wrong choice!")
                error = True

            if results_number.isnumeric():
                print("should work?")
                settings_config["search"]["results_number"] = int(results_number)
            else:
                print("has failed")
                error = True
                self.RESULTS_NUMBER_choice.delete(0, "end")
                self.RESULTS_NUMBER_choice.insert(
                    0, 
                    str(settings_config["search"]["results_number"])
                )

            if thumbnail_quality in thumbnail_qualities:
                settings_config["search"]["thumbnail_quality"] = \
                    thumbnail_qualities.index(thumbnail_quality)

            if not error:
                write_to_file()
        
        def cc():
            self.results = {}
            self.save()
            self.resultsshow()
        
        if hasattr(self, 'stt') and self.stt.winfo_exists():
            self.stt.destroy()
            return
        
        self.stt = ctk.CTkToplevel(self)
        self.stt.geometry("300x550")
        self.stt.title("settings")
        self.stt.resizable(False, False)
        
        title_frame = ctk.CTkFrame(self.stt)
        title_frame.pack(padx=5, pady=5, fill="x")
        title = ctk.CTkLabel(
            title_frame, 
            text="settings", 
            font=('Arial', 20, "bold"), 
            wraplength=250
        )
        title.pack(padx=5, pady=5)

        UI_frame = ctk.CTkFrame(self.stt)
        UI_frame.pack(padx=5, pady=(0, 5), fill="x")

        UI_title_frame = ctk.CTkFrame(UI_frame)
        UI_title_frame.pack(padx=5, pady=(5, 0), fill="x")
        UI_title = ctk.CTkLabel(
            UI_title_frame, 
            text="UI", 
            font=('Arial', 20, "bold"), 
            wraplength=250
        )
        UI_title.pack(padx=5, pady=5)
        
        UI_options_frame = ctk.CTkFrame(UI_frame)
        UI_options_frame.pack(padx=5, pady=5, fill="x")

        main_color_frame = ctk.CTkFrame(UI_options_frame)
        main_color_frame.pack(padx=5, pady=5, fill="x")
        main_color_label = ctk.CTkLabel(main_color_frame, text="main_color:")
        main_color_label.pack(padx=20, pady=5, side="left")
        self.main_color_choice = ctk.CTkEntry(
            main_color_frame, 
            placeholder_text="HEX color"
        )
        self.main_color_choice.pack(padx=5, pady=5, side="right")
        self.main_color_choice.insert(0, settings_config["ui"]["main_color"])

        second_color_frame = ctk.CTkFrame(UI_options_frame)
        second_color_frame.pack(padx=5, pady=5, fill="x")
        second_color_label = ctk.CTkLabel(second_color_frame, text="second_color:")
        second_color_label.pack(padx=20, pady=5, side="left")
        self.second_color_choice = ctk.CTkEntry(
            second_color_frame, 
            placeholder_text="HEX color"
        )
        self.second_color_choice.pack(padx=5, pady=5, side="right")
        self.second_color_choice.insert(0, settings_config["ui"]["second_color"])

        SEARCH_frame = ctk.CTkFrame(self.stt)
        SEARCH_frame.pack(padx=5, pady=(0, 5), fill="x")

        SEARCH_title_frame = ctk.CTkFrame(SEARCH_frame)
        SEARCH_title_frame.pack(padx=5, pady=(5, 0), fill="x")
        SEARCH_title = ctk.CTkLabel(
            SEARCH_title_frame, 
            text="SEARCH", 
            font=('Arial', 20, "bold"), 
            wraplength=250
        )
        SEARCH_title.pack(padx=5, pady=5)
        
        SEARCH_options_frame = ctk.CTkFrame(SEARCH_frame)
        SEARCH_options_frame.pack(padx=5, pady=5, fill="x")

        RESULTS_NUMBER_frame = ctk.CTkFrame(SEARCH_options_frame)
        RESULTS_NUMBER_frame.pack(padx=5, pady=5, fill="x")
        RESULTS_NUMBER_label = ctk.CTkLabel(
            RESULTS_NUMBER_frame, 
            text="results number:"
        )
        RESULTS_NUMBER_label.pack(padx=20, pady=5, side="left")
        self.RESULTS_NUMBER_choice = ctk.CTkEntry(
            RESULTS_NUMBER_frame, 
            placeholder_text="number"
        )
        self.RESULTS_NUMBER_choice.pack(padx=5, pady=5, side="right")
        self.RESULTS_NUMBER_choice.insert(
            0, 
            str(settings_config["search"]["results_number"])
        )

        thumb_quality_frame = ctk.CTkFrame(SEARCH_options_frame)
        thumb_quality_frame.pack(padx=5, pady=(5, 5), fill="both")
        labeltq = ctk.CTkLabel(
            thumb_quality_frame, 
            text="thumbnail quality:"
        )
        labeltq.pack(padx=20, pady=(0, 0), fill="both", side="left")
        self.thumb_quality_option = ctk.CTkOptionMenu(
            thumb_quality_frame, 
            values=thumbnail_qualities
        )
        self.thumb_quality_option.set(
            thumbnail_qualities[settings_config["search"]["thumbnail_quality"]]
        )
        self.thumb_quality_option.pack(pady=5, padx=5, side="right")

        last_frame = ctk.CTkFrame(self.stt)
        last_frame.pack(padx=5, pady=5, fill="x", side="bottom")
        clear_cache = ctk.CTkButton(last_frame, text="clear cache", command=cc)
        clear_cache.pack(padx=5, pady=5, side="left")
        save_settings = ctk.CTkButton(
            last_frame, 
            text="save", 
            command=save_settings_
        )
        save_settings.pack(padx=5, pady=5, side="right")


if __name__ == "__main__":
    app_instance = App()
    app_instance.mainloop()
