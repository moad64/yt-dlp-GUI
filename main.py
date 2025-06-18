import customtkinter as tk 
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

main_folder = f"{os.path.expanduser("~")}/.yt-dlp-GUI"
if not os.path.exists(main_folder) :
    os.makedirs(main_folder)
if not os.path.exists(f"{main_folder}/thumb") :
    os.makedirs(f"{main_folder}/thumb")
if not os.path.exists(f"{main_folder}/download") :
    os.makedirs(f"{main_folder}/download")
data_file_path = f"{main_folder}/data.json"
try :
    with open(data_file_path, "r") as f :
        results = json.load(f)
except Exception as e :
        print()
        results = {}
def save() :
    with open(data_file_path, "w") as f :
        json.dump(results, f, indent = 4)


tk.set_appearance_mode("dark")  # "light", "dark", or "system"
tk.set_default_color_theme("dark-blue")  # "blue", "green", "dark-blue", etc.

class app(tk.CTk):
   def __init__(self):
        super().__init__()
        self.download_functionality = True
        if shutil.which("ffmpeg") is None:
            self.error("FFmpeg is not installed! \n please install it to enable downloading functionality")
            self.download_functionality = False

        self.title("yt-dlp GUI")
        self.geometry("720x420")
        self.resizable(False, False)
        self.configure(bg="black")

        title_frame = tk.CTkFrame(self)
        title_frame.pack(padx=5 , pady= 5, side="top", fill="x")
        label = tk.CTkLabel(title_frame, text="Welcome to yt-dlp GUI!", font=("Classic Console", 50), text_color = "blue")
        label.pack(pady=20)
        
        search_frame = tk.CTkFrame(self)
        search_frame.pack(padx=5, pady=5, fill="x")
        self.search = tk.CTkEntry(search_frame, placeholder_text="Search for a video or playlist")
        self.search.bind("<KP_Enter>", self.on_press)
        self.search.focus_set()
        self.search.pack(side="left", padx=10, pady=10, fill="x", expand=True)

        search_button = tk.CTkButton(search_frame, text="Search", command=self.search_yt, hover_color = "blue")
        search_button.pack(side="right", pady=10, padx=10)

        self.results_frame = tk.CTkScrollableFrame(self)
        self.results_frame.pack(padx=5, pady=5, fill="both", expand=True)
        if results :
            self.resultsshow()
        self.results_frame._parent_canvas.bind("<Enter>", self._bind_mousewheel_linux)
        self.results_frame._parent_canvas.bind("<Leave>", self._unbind_mousewheel_linux)

   def _bind_mousewheel_linux(self, event):
        self.results_frame._parent_canvas.bind_all("<Button-4>", self._on_mousewheel_linux)
        self.results_frame._parent_canvas.bind_all("<Button-5>", self._on_mousewheel_linux)

   def _unbind_mousewheel_linux(self, event):
          self.results_frame._parent_canvas.unbind_all("<Button-4>")
          self.results_frame._parent_canvas.unbind_all("<Button-5>")

   def _on_mousewheel_linux(self, event):
          direction = -1 if event.num == 4 else 1
          self.results_frame._parent_canvas.yview_scroll(direction, "units")

   def truncate_title(self, title, max_length=30):
            return title[:max_length] + "..." if len(title) > max_length else title
   def on_press(self, event=None) :
        print("Enter key pressed!")
        self.search_yt()
   def clean_cache(self) :
            used_thumps = {thump["thumb_path"] for thump in results.values()}
            directory = f"{main_folder}/thumb"
            for filename in os.listdir(directory) :
                file_path = os.path.join(directory, filename)
                if file_path not in used_thumps :
                    os.unlink(file_path)

   def destroy_widgets(self) :
        for widget in self.results_frame.winfo_children():
               widget.destroy()

   def resultsshow(self) :
          
          for idx, result in enumerate(results.values()) :
            row = idx // 3
            col   = idx % 3
            result_frame = tk.CTkFrame(self.results_frame, fg_color = "#424042", border_color = "blue", border_width = 2, height = 250)
            result_frame.grid(row = row, column = col, padx=5, pady=5, sticky="n")
            result_frame.grid_propagate(False)

            if os.path.exists(result["thumb_path"]) :
                img = Image.open(result["thumb_path"])
                img = img.resize((200, 100))
                ctk_image = tk.CTkImage(img, size=(200, 100))
            else :
                ctk_image = None
            self.thumbnail_label = tk.CTkLabel(result_frame, image=ctk_image, text="")
            self.thumbnail_label.pack(pady=10, padx=10)
            self.video_title = tk.CTkLabel(result_frame, text=self.truncate_title(str(result["title"])), font=("Arial", 16), wraplength=200)
            self.video_title.pack(pady=10, padx=10, fill = "both", expand = True)
            self.watch = tk.CTkButton(result_frame, text = "watch", command = lambda  url = result["url"] :  (os.system("pkill vlc"), subprocess.Popen(["vlc", url])), hover_color = "blue")
            self.watch.pack(pady=5, padx=5, fill = "x")
            if self.download_functionality :
                self.download = tk.CTkButton(result_frame, text = "download", hover_color = "blue", command = lambda current = result : self.download_window(current))
                self.download.pack(pady = (0, 6), padx = 5, fill = "x", side = "bottom")

   def download_window(self, result) :
       dw = tk.CTkToplevel(self)
       dw.geometry("300x550")
       dw.title("download")
       dw.resizable(False, False)
       title_frame = tk.CTkFrame(dw)
       title_frame.pack(padx=5, pady=5, fill="x")
       title = tk.CTkLabel(title_frame, text = f"{result["title"][:30]} ...", font = ('Arial', 20), wraplength = 250)
       title.pack(padx=5, pady=5)
       thumb_frame = tk.CTkFrame(title_frame)
       thumb_frame.pack(padx=10, pady=(0, 10), expand=True, fill = "both")
       if os.path.exists(result["thumb_path"]) :
                img = Image.open(result["thumb_path"])
                img = img.resize((250, 125))
                ctk_image = tk.CTkImage(img, size=(250, 125))
       else :
                ctk_image = None
       thumbnail_label = tk.CTkLabel(thumb_frame, image=ctk_image, text="")
       thumbnail_label.pack(pady=10, padx=10)
       options_frame = tk.CTkFrame(dw)
       options_frame.pack(padx=5, pady=(0, 5), fill = "both" )
       vora_frame = tk.CTkFrame(options_frame)
       vora_frame.pack(padx=5, pady=5, fill = "both")
       video_label = tk.CTkLabel(vora_frame, text="video")
       video_label.pack(padx=20, pady=5, side = "left")
       self.v_check = tk.CTkCheckBox(vora_frame, text = "")
       self.v_check.pack(padx=0, pady=5, side = "right")
       dq_frame = tk.CTkFrame(options_frame)
       dq_frame.pack(padx=5, pady=(5, 5), fill = "both")
       resolutions = []
       fpss = []
       protocols = []
       a_qualities = []
       for vid in result["videos"].values() :
           resolutions.append(vid["resolution"])
           fpss.append(vid["fps"])
           protocols.append(vid["protocol"])
       for aud in result["audios"].values() :
           a_qualities.append(aud["quality"])


       labelone = tk.CTkLabel(dq_frame, text = "quality :")
       labelone.pack(padx=20, pady=(0, 0), fill = "both", side = "left")
       self.quality_option = tk.CTkOptionMenu(dq_frame, values=[ str(r) for r in self.listing(resolutions)])
       self.quality_option.set("720")  # default value
       self.quality_option.pack(pady=5, padx = 5, side = "right")

       df_frame = tk.CTkFrame(options_frame)
       df_frame.pack(padx=5, pady=(0, 5), fill = "both")
       labeltwo = tk.CTkLabel(df_frame, text = "frame_rate :")
       labeltwo.pack(padx=20, pady=(0, 0), fill = "both", side = "left")
       self.fps_option = tk.CTkOptionMenu(df_frame, values=[ str(int(r)) for r in self.listing(fpss)])
       self.fps_option.set(str(int(self.listing(fpss)[0])))  # default value
       self.fps_option.pack(pady=5, padx = 5, side = "right")

       dp_frame = tk.CTkFrame(options_frame)
       dp_frame.pack(padx=5, pady=(0, 5), fill = "both")
       labelthree = tk.CTkLabel(dp_frame, text = "protocol :")
       labelthree.pack(padx=20, pady=(0, 0), fill = "both", side = "left")
       self.prtc_option = tk.CTkOptionMenu(dp_frame, values=self.listing(protocols))
       self.prtc_option.set(self.listing(protocols)[0])  # default value
       self.prtc_option.pack(pady=5, padx = 5, side = "right")
       a_options_frame = tk.CTkFrame(dw)
       a_options_frame.pack(padx=5, pady=(0, 5), fill = "both" )
       vora_frame2 = tk.CTkFrame(a_options_frame)
       vora_frame2.pack(padx=5, pady=5, fill = "both")
       audeo_label = tk.CTkLabel(vora_frame2, text="audio")
       audeo_label.pack(padx=20, pady=5, side = "left")
       self.a_check = tk.CTkCheckBox(vora_frame2, text = "")
       self.a_check.pack(padx=0, pady=5, side = "right")
       daq_frame = tk.CTkFrame(a_options_frame)
       daq_frame.pack(padx=5, pady=(5, 5), fill = "both")
       labelaq = tk.CTkLabel(daq_frame, text = "audio quality :")
       labelaq.pack(padx=20, pady=(0, 0), fill = "both", side = "left")
       self.a_quality_option = tk.CTkOptionMenu(daq_frame, values=[ str(r) for r in self.listing(a_qualities)])
       self.a_quality_option.set(str(self.listing(a_qualities)[0]))  # default value
       self.a_quality_option.pack(pady=5, padx = 5, side = "right")
       check = tk.CTkButton(dw, text = "download", command = lambda current = result : self.getting_download(current))
       check.pack(padx=5, pady=5)
   def getting_download(self, result) :
       if hasattr(self, 'error_window') and self.error_window.winfo_exists():
           self.error_window.destroy()
       if self.v_check.get() and not self.a_check.get():
            for key, vid in result["videos"].items() :
                found = False
                if vid["resolution"] == int(self.quality_option.get()) and vid["fps"] == int(self.fps_option.get()) and vid["protocol"] == self.prtc_option.get() :
                        print(f"it's {key}")
                        found = True
                        self.start_downloading(vid["url"], vid["extension"], f"{self.sanitize_filename(result["title"])}_VIDEO")
                        break
            if not found :
                self.error("No video was found, try another combination 🙂")
                return
       elif self.a_check.get() and not self.v_check.get() :
           for key, aud in result["audios"].items() :
               found = False
               if aud["quality"] == self.a_quality_option.get() :
                   print(f"it's {key}")
                   found = True
                   self.start_downloading(aud["url"], aud["extension"], f"{self.sanitize_filename(result["title"])}_AUDIO")
                   break
           if not found :
               self.error("No audio was found, try another combination 🙂")
               return
       elif self.v_check.get() and self.a_check.get() :
            for key, vid in result["videos"].items() :
                v_found = False
                if vid["resolution"] == int(self.quality_option.get()) and vid["fps"] == int(self.fps_option.get()) and vid["protocol"] == self.prtc_option.get() :
                        print(f"it's {key}")
                        v_found = True
                        v_url = vid["url"]
                        v_ext = vid["extension"]
                        break
            if not v_found :
                      self.error("No video was found, try another combination 🙂")
                      return
            for key, aud in result["audios"].items() :
                    a_found = False
                    if aud["quality"] == self.a_quality_option.get() :
                        print(f"it's {key}")
                        a_found = True
                        a_url = aud["url"]
                        a_ext = aud["extension"]
                        break
            if not a_found :
                          self.error("No audio was found, try another combination 🙂")
                          return
            if a_found and v_found :
               video_path = filedialog.asksaveasfilename(
               initialfile = f"{f"{self.sanitize_filename(result["title"])}_VIDEO"}.{v_ext}",
               defaultextension=f".{v_ext}",  # or ".webm", etc.
               filetypes=[(f"{v_ext.upper()} files", f"*.{v_ext}"), ("All files", "*.*")],
               title="Choose where to save")
               if video_path:
                    self.video_folder = os.path.dirname(video_path)
                    self.v_path = video_path
                    self.video_thread = threading.Thread(target=self.saving, args=(v_url, v_ext, result["title"], video_path, "video"))
                    self.video_thread.start()

                    def wait_and_download_audio():
                        self.video_thread.join()
                        if not os.path.exists(self.v_path) :
                            self.error("video download failed so the audio skipped")
                            return
                        audio_path = os.path.join(self.video_folder, f"{f"{self.sanitize_filename(result["title"])}_AUDIO"}.{a_ext}")
                        self.a_path = audio_path
                        self.audio_thread = threading.Thread(target=self.saving, args=(a_url, a_ext, result["title"], audio_path, "audio"))
                        self.audio_thread.start()

                    threading.Thread(target=wait_and_download_audio).start()


            else :
              print("error")


   def error(self, error) :
                   #msgbox.showerror("Error", "Nothing was found, try another combination 🙂")
                    self.error_window = tk.CTkToplevel(self)
                    self.error_window.geometry("300x150")
                    self.error_window.title("Error")
                    self.error_window.resizable(False, False)

                    label = tk.CTkLabel(self.error_window, text=error, text_color="red", font=("Arial", 16), wraplength =250)
                    label.pack(pady=20)

                    ok_button = tk.CTkButton(self.error_window, text="OK", command=self.error_window.destroy)
                    ok_button.pack(pady=10)
   def start_downloading(self, url, ext, title, type = None) :
       if not type or type == "video" :
        video_path = filedialog.asksaveasfilename(
        initialfile = f"{title}.{ext}",
        defaultextension=f".{ext}",  # or ".webm", etc.
        filetypes=[(f"{ext.upper()} files", f"*.{ext}"), ("All files", "*.*")],
        title="Choose where to save")
        self.video_folder = os.path.dirname(video_path)
        self.video_thread = threading.Thread(target=self.saving, args=(url, ext, title, video_path, type))
        self.video_thread.start()
       elif type == "audio" :
           def wait() :
               if hasattr(self, 'video_thread'):
                   self.video_thread.join()
               audio_path = os.path.join(self.video_folder, f"{title}.{ext}")
               audio_thread = threading.Thread(target=self.saving, args=(url, ext, title, audio_path, type))
               audio_thread.start()
           self.audio_thread = threading.Thread(target=wait)
           self.audio_thread.start()
       elif type == None :
           save_path = filedialog.asksaveasfilename(
           initialfile = f"{title}.{ext}",
           defaultextension=f".{ext}",  # or ".webm", etc.
           filetypes=[(f"{ext.upper()} files", f"*.{ext}"), ("All files", "*.*")],
           title="Choose where to save")
           self.thread = threading.Thread(target=self.saving, args=(url, ext, title, self.save_path, type))
           self.thread.start()

   def saving(self, url, ext, title, save_path, type) :
       if save_path :
               print(save_path)
               response = requests.get(url, stream=True, timeout = 10)
               ydl_opts = {
                'outtmpl': save_path,
                'quiet': False,
                'noplaylist': True
                }
               try :
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            ydl.download([url])
               except Exception as e :
                   self.error(f"{type} download failed - {e}")
                   return
               print("Download complete.")
               # Open folder after download

               if type not in ["video", "audio"] :
                   folder = os.path.dirname(save_path)
                   subprocess.Popen(["thunar", folder])  # Linux o
               if type == "video" :
                   self.v_path = save_path
               elif type == "audio":
                   self.a_path = save_path
                   self.merging(self.v_path, self.a_path)
   def merging(self, video, audio) :
       print(f"video : {video}")
       print(f"audio : {audio}")
       output_path = video.replace("_VIDEO", "")
       command = [
        "ffmpeg",
        "-i", video,
        "-i", audio,
        "-c:v", "copy",  # copy video codec
        "-c:a", "aac",   # encode audio to AAC
        "-strict", "experimental",
        output_path
        ]

       subprocess.run(command)
       print("Merging complete.")
       os.remove(video)
       os.remove(audio)
       subprocess.Popen(["thunar", os.path.dirname(output_path)])

   def listing(self, list) :
       fl = []
       for item in list :
           if item not in fl :
               fl.append(item)

       return fl
   def sanitize_filename(self, name):
                    title = re.sub(r'[^\w\-_\. ]', '_', name)
                    title = title.strip().replace(' ', '_')
                    return title[:30]
   def search_yt(self):
    self.clean_cache()
    for i in range(9) :
        results[f"result{i}"] = {}
    self.search_progress = tk.CTkProgressBar(self, width=200)
    self.search_progress.pack(pady=10)
    self.search_progress.start()
    def do_search():
        self.failed = False
        query = f"ytsearch9:{self.search.get()}"
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'format': 'best',
        }
        try :
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(query, download=False)
        except Exception as e :
            self.error(f"Error : {e}")
            self.failed = True
            return

        for entry, result in zip(info['entries'], results.values()):
                result["title"] = entry["title"]
                result["url"] = entry["url"]
                formats = entry.get("formats", [])
                video_formats = [f for f in formats if f.get("vcodec") != "none" and f.get("acodec") == "none"]
                audio_formats = [f for f in formats if f.get("acodec") != "none" and f.get("vcodec") == "none"]
                result["videos"] = {}
                for i, vid in enumerate(video_formats) :
                      result["videos"][f"video{i}"] = {
                          "resolution" : vid["height"],
                          "url" : vid["url"],
                          "protocol" : vid["protocol"],
                          "fps" : vid["fps"],
                          "extension" : vid["ext"]
                          }
                result["audios"] = {}
                for i, aud in enumerate(audio_formats) :
                    result["audios"][f"audio{i}"] = {
                        "quality" : aud["format_note"],
                        "extension" : aud["audio_ext"],
                        "url" : aud["url"],
                        "protocol" : aud["protocol"]
                        }

                if 'thumbnails' in entry and entry['thumbnails']:
                    best_thumb = max(entry['thumbnails'], key=lambda t: t.get('width', 0))
                    thumb_url = best_thumb['url']
                else:
                    thumb_url = entry.get('thumbnail')

                response = requests.get(thumb_url, timeout = 10)
                result["thumb_path"] = os.path.join(main_folder, "thumb", f"{self.sanitize_filename(result['title'])}.png")
                with open(result["thumb_path"], "wb") as f:
                    f.write(response.content)




        # Update GUI in main thread
        self.search_progress.stop()
        self.search_progress.pack_forget()
        if not self.failed :
            self.destroy_widgets()
            self.resultsshow()
            save()

    threading.Thread(target=do_search).start()


if __name__ == "__main__":
    app_instance = app()
    app_instance.mainloop()



