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
from concurrent.futures import ThreadPoolExecutor
import time
import sys
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from PIL import ImageColor

main_folder = f"{os.path.expanduser("~")}/.yt-dlp-GUI"
if not os.path.exists(main_folder) :
	os.makedirs(main_folder)
if not os.path.exists(f"{main_folder}/thumb") :
	os.makedirs(f"{main_folder}/thumb")
if not os.path.exists(f"{main_folder}/download") :
	os.makedirs(f"{main_folder}/download")
data_file_path = f"{main_folder}/data.json"
settings_config_file_path = f"{main_folder}/settings.json"
try :
	with open(data_file_path, "r") as f :
		data = json.load(f)
		results = data["results"]
		playlist_title = data["playlist_title"]
except Exception as e :
		print(e)
		data = {}
		results = {}
		playlist_title = None
try :
	with open(settings_config_file_path, "r") as f :
		settings_config = json.load(f)
except Exception :
	settings_config = {
            "ui" : {
                "main_color" : "blue",
                    "second_color" : "black"
				},
			"search" : {
				"results_number" : 9,
				"thumbnail_quality" : 0
				} 
            }



tk.set_appearance_mode("dark")	# "light", "dark", or "system"
#tk.set_default_color_theme(settings_config["ui"]["main_color"])  # "blue", "green", "dark-blue", etc.

class app(tk.CTk):
	def __init__(self):
		super().__init__()
		self.results = results
		self.playlist_title = playlist_title
		self.download_functionality = True

		self.title("yt-dlp GUI")
		self.geometry("720x465")
		self.resizable(False, False)
		self.configure(bg="black")

		title_frame = tk.CTkFrame(self)
		title_frame.pack(padx=5 , pady= 5, side="top", fill="x")
		title_frame.bind("<Button-1>", self.settings)
		label = tk.CTkLabel(title_frame, text="Welcome to yt-dlp GUI!", font=("Classic Console", 50), text_color = settings_config["ui"]["main_color"])
		label.pack(pady=20)
		
		search_frame = tk.CTkFrame(self)
		search_frame.pack(padx=5, pady=5, fill="x")
		self.search = tk.CTkEntry(search_frame, placeholder_text="Enter URL or search term")
		self.search.bind("<KP_Enter>", self.on_press)
		self.search.focus_set()
		self.search.pack(side="left", padx=10, pady=10, fill="x", expand=True)

		search_button = tk.CTkButton(search_frame, text="Search", command=self.search_yt, fg_color = settings_config["ui"]["main_color"],  hover_color = settings_config["ui"]["second_color"])
		search_button.pack(side="right", pady=10, padx=10)

		self.results_frame = tk.CTkScrollableFrame(self)
		self.results_frame.pack(padx=5, pady=5, fill="both", expand=True)
		if self.results :
			self.resultsshow()
		self.results_frame._parent_canvas.bind("<Enter>", self._bind_mousewheel_linux)
		self.results_frame._parent_canvas.bind("<Leave>", self._unbind_mousewheel_linux)

		if shutil.which("ffmpeg") is None:
			self.error("FFmpeg is not installed! \n please install it to enable downloading functionality")
			self.download_functionality = False
	def save(self) :
			data["results"] = self.results
			data["playlist_title"] = self.playlist_title
			with open(data_file_path, "w") as f :
				json.dump(data, f, indent = 4)
	def _bind_mousewheel_linux(self, event):
		self.results_frame._parent_canvas.bind_all("<Button-4>", self._on_mousewheel_linux)
		self.results_frame._parent_canvas.bind_all("<Button-5>", self._on_mousewheel_linux)

	def _unbind_mousewheel_linux(self, event):
		self.results_frame._parent_canvas.unbind_all("<Button-4>")
		self.results_frame._parent_canvas.unbind_all("<Button-5>")

	def _on_mousewheel_linux(self, event):
		direction = -1 if event.num == 4 else 1
		self.results_frame._parent_canvas.yview_scroll(direction, "units")

	def truncate_title(self, title, max_length=75):
		return title[:max_length] + "..." if len(title) > max_length else title #f"{title}{' ' * (max_length - len(title))}"
	def on_press(self, event=None) :
		print("Enter key pressed!")
		self.search_yt()
	def clean_cache(self) :
		used_thumps = {thump["thumb_path"] for thump in self.results.values()}
		directory = f"{main_folder}/thumb"
		for filename in os.listdir(directory) :
			file_path = os.path.join(directory, filename)
			if file_path not in used_thumps :
				os.unlink(file_path)

	def destroy_widgets(self) :
		for widget in self.results_frame.winfo_children():
			widget.destroy()
		if hasattr(self, 'pl_card_frame') and self.pl_card_frame.winfo_exists():
			self.pl_card_frame.destroy()
	
	
	def fetching_playlist_downloads(self):
		# Initialize storage for common properties
		v_extensions = []
		resolutions = []
		v_codecs = []
		fpss = []
		protocols = []
		a_qualities = []
		a_extensions = []
    
		# Lock for thread-safe operations
		lock = threading.Lock()
    
		# Dictionary to store formats for each video
		all_formats = {}
		errors = []
    
		def fetch_video_formats(url, index):
			"""Fetch available formats for a single video."""
			try:
				ydl_opts = {
					'quiet': True,
					'no_warnings': True,
					'extract_flat': False,  # Need full info for formats
					'skip_download': True,
				}	
            
				with yt_dlp.YoutubeDL(ydl_opts) as ydl:
					info = ydl.extract_info(url, download=False)
					
					# Get all available formats
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
    
		# Create and start threads for each URL
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
    
		# Wait for all threads to complete
		for thread in threads:
			thread.join()
    
		print(f"\nFetching complete. Success: {len(all_formats)}, Errors: {len(errors)}")
    
		# If we have successful fetches, find common formats
		if all_formats:
			# Find videos with formats
			videos_with_formats = [data for data in all_formats.values() if data['success']]
        
			if not videos_with_formats:
				print("No videos have format information.")
				return
        
			# Extract unique properties from first video
			first_video = videos_with_formats[0]
			all_video_formats = first_video['formats']
        
			# Initialize sets with properties from first video
			common_v_extensions = set()
			common_resolutions = set()
			common_v_codecs = set()
			common_fpss = set()
			common_protocols = set()
			common_a_qualities = set()
			common_a_extensions = set()
			
			# Helper function to extract format properties
			def extract_format_properties(format_list):
				v_exts = set()
				res = set()
				v_codes = set()
				fps_set = set()
				protos = set()
				a_quals = set()
				a_exts = set()
				
				for fmt in format_list:
					# Video properties
					if fmt.get('vcodec') != 'none':  # Has video
						# Extension
						if fmt.get('ext'):
							v_exts.add(fmt['ext'])
                    
						# Resolution
						if fmt.get('height'):
							resolution = f"{fmt.get('width', '?')}x{fmt['height']}"
							res.add(resolution)
						
						# Video codec
						if fmt.get('vcodec') and fmt['vcodec'] != 'none':
							# Simplify codec name
							codec = fmt['vcodec'].split('.')[0]
							if codec and codec != 'none':
								v_codes.add(codec)
						
						# FPS
						if fmt.get('fps'):
							fps_set.add(str(fmt['fps']))
					
					# Audio properties
					if fmt.get('acodec') != 'none':  # Has audio
						# Audio quality
						if fmt.get('asr'):
							a_quals.add(str(fmt['asr']))
						
						# Audio codec/extension
						if fmt.get('acodec') and fmt['acodec'] != 'none':
							# Extract audio format from codec
							acodec = fmt['acodec'].split('.')[0]
							if acodec:
								a_exts.add(acodec)
					
						# Protocol
					if fmt.get('protocol'):
						protos.add(fmt['protocol'])
				
				return v_exts, res, v_codes, fps_set, protos, a_quals, a_exts
			
			# Get properties from first video
			(common_v_extensions, common_resolutions, common_v_codecs, common_fpss, common_protocols, common_a_qualities, common_a_extensions) = extract_format_properties(all_video_formats)
			
			# Compare with remaining videos
			for video_data in videos_with_formats[1:]:
				formats = video_data['formats']
				
				(v_exts, res, v_codes, fps_set, protos, a_quals, a_exts) = extract_format_properties(formats)
				
				# Find intersection (common properties)
				common_v_extensions &= v_exts
				common_resolutions &= res
				common_v_codecs &= v_codes
				common_fpss &= fps_set
				common_protocols &= protos
				common_a_qualities &= a_quals
				common_a_extensions &= a_exts
			
			# Convert sets to sorted lists
			v_extensions = sorted(common_v_extensions)
			resolutions = sorted(common_resolutions, key=lambda x: (int(x.split('x')[1]) if 'x' in x else 0, x))
			v_codecs = sorted(common_v_codecs)
			fpss = sorted(common_fpss, key=lambda x: float(x) if x.replace('.', '').isdigit() else 0)
			protocols = sorted(common_protocols)
			a_qualities = sorted(common_a_qualities, 
                           key=lambda x: int(x) if x.isdigit() else 0)
			a_extensions = sorted(common_a_extensions)
        
			# Display results
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
        
			# Store in instance variables if needed
			self.common_formats = {
				'v_extensions': v_extensions,
				'resolutions': resolutions,
				'v_codecs': v_codecs,
				'fpss': fpss,
				'protocols': protocols,
				'a_qualities': a_qualities,
				'a_extensions': a_extensions
				}	
			self.after(0, lambda : self.options_show(None))
			
	def resultsshow(self) :	
		self.destroy_widgets()
		for idx, result in enumerate(self.results.values()) :
			row = idx // 3
			col	  = idx % 3
			result_frame = tk.CTkFrame(self.results_frame, fg_color = "#424042", border_color = settings_config["ui"]["second_color"], border_width = 2, height = 250)
			result_frame.grid(row = row, column = col, padx=5, pady=5, sticky="n")
			result_frame.grid_propagate(False)

			if os.path.exists(result["thumb_path"]) :
				img = Image.open(result["thumb_path"])
				img = img.resize((200, 100))
				ctk_image = tk.CTkImage(img, size=(200, 100))
			else :
				ctk_image = None
			self.thumbnail_label = tk.CTkLabel(result_frame, image=ctk_image, text="")
			self.thumbnail_label.pack(pady=6, padx=10)
			self.video_title = tk.CTkLabel(result_frame, text=self.truncate_title(str(result["title"])), font=("Arial", 15), wraplength=200, height=75)
			self.video_title.pack(pady=0, padx=10, fill = "both", expand = True)
			#self.watch = tk.CTkButton(result_frame, text = "watch", command = lambda  url = result["url"] :  (os.system("pkill vlc"), subprocess.Popen(["vlc", url])), hover_color = "blue")
			#self.watch.pack(pady=5, padx=5, fill = "x")
			self.download = tk.CTkButton(result_frame, text = "download or watch", fg_color = settings_config["ui"]["main_color"], hover_color = settings_config["ui"]["second_color"], command = lambda current = result : self.download_window(current))
			self.download.pack(pady = (0, 6), padx = 5, fill = "x", side = "bottom")
		
		if self.playlist_title :
			self.pl_card_frame = tk.CTkFrame(self, fg_color=settings_config["ui"]["main_color"])
			self.pl_card_frame.pack(padx=5, pady=(0, 5), fill = "both")
			pl_title_label = tk.CTkLabel(self.pl_card_frame, text=self.playlist_title, font=("Arial", 20, "bold"))
			pl_title_label.pack(padx=10, pady=5, side = "left")
			
			p_label = tk.CTkLabel(self.pl_card_frame, text="- playlist", font=("Arial", 15))
			p_label.pack(padx=0, pady=5, side = "left")
			
			#d_button = tk.CTkButton(self.pl_card_frame, text="download options", text_color=settings_config["ui"]["main_color"], command=lambda: self.download_window(None) , fg_color = settings_config["ui"]["second_color"])
			#d_button.pack(side="right", pady=10, padx=10, fill="y")
		
	def animate_loading(self, label, count=0):
		if not self.loading_animation :
			return
		dots = '.' * (count % 4)
		label.configure(text=f"Loading{dots}")
		self.after(500, lambda: self.animate_loading(label, count + 1))
	def download_window(self, result) :
		global dw
		dw = tk.CTkToplevel(self)
		dw.geometry("300x700")
		dw.title("download")
		dw.resizable(False, False)
		dw.attributes('-type', 'dialog')
		title_frame = tk.CTkFrame(dw)
		title_frame.pack(padx=5, pady=5, fill="x")
		
		if not self.download_functionality :
			ndf = tk.CTkLabel(dw, text = "NO DOWNLOAD FUNCTIONALITY !\nplease install ffmpeg")
			ndf.place(relx = 0.5, rely = 0.5, anchor = "center")
			return
		
		if result :
			title = tk.CTkLabel(title_frame, text = f"{result["title"][:75]} ...", font = ('Arial', 15), wraplength = 250)
			title.pack(padx=5, pady=5)
			thumb_frame = tk.CTkFrame(title_frame)
			thumb_frame.pack(padx=10, pady=(0, 10), expand=True, fill = "both")
			if os.path.exists(result["thumb_path"]) :
				img = Image.open(result["thumb_path"])
				img = img.resize((250, 125))
				ctk_image = tk.CTkImage(img, size=(250, 125))
			else :
				ctk_image = None
			self.thumbnail_label = tk.CTkLabel(thumb_frame, image=ctk_image, text="", font = ('Arial', 50), text_color = settings_config["ui"]["second_color"])
			self.thumbnail_label.pack(pady=10, padx=10)
			self.options_frame = tk.CTkFrame(dw)
			self.options_frame.pack(padx=5, pady=(0, 5), expand = True, fill = "both" )
			
			if (result.get("audios") and result.get("videos")) and  self.download_functionality :
				self.loading_animation = False
				self.thumbnail_label.configure(text = "▶️", font = ('Arial', 50), text_color = settings_config["ui"]["second_color"])
				self.thumbnail_label.bind("<Button-1>", lambda  e, url = result["url"] :	 (os.system("pkill vlc"), subprocess.Popen(["vlc", url])))
				self.options_show(result)
			elif (not result.get("audios") and not result.get("videos")) and	 self.download_functionality :
				self.thumbnail_label.configure(text = "loading...", font = ('Arial', 15))
				self.loading = tk.CTkLabel(self.options_frame, text = "loading...")
				self.loading.place(relx=0.5, rely = 0.5, anchor = "center")
				self.loading_animation = True
				self.animate_loading(self.loading)
				threading.Thread(target = self.fetching_downloads, args = (result, )).start()
		else :
			
			title = tk.CTkLabel(title_frame, text = self.playlist_title, font = ('Arial', 15), wraplength = 250)
			title.pack(padx=5, pady=5)
			self.options_frame = tk.CTkFrame(dw)
			self.options_frame.pack(padx=5, pady=(0, 5), expand = True, fill = "both" )
			
			if (self.results.get("audios") and self.results.get("videos")) and  self.download_functionality :
				self.loading_animation = False
				self.options_show(result=None)
			elif (not self.results.get("audios") and not self.results.get("videos")) and	 self.download_functionality :
				self.loading = tk.CTkLabel(self.options_frame, text = "loading playlist ...")
				self.loading.place(relx=0.5, rely = 0.5, anchor = "center")
				self.loading_animation = True
				self.animate_loading(self.loading)
				threading.Thread(target = self.fetching_playlist_downloads).start()
			
		
	
	def fetching_downloads(self, result, jfs = False) :
		ydl_opts = {
			'quiet': True,
			'skip_download': True,
			'format': 'best',
			'cookies_from_browser': 'brave',
			'extractor_args': {
				'youtube': {
					'player_client': ['tv'],  # Try different clients
					'player_skip': ['configs'],  # Skip some configs
					}
				}
			}
		try :
			with yt_dlp.YoutubeDL(ydl_opts) as ydl:
				info = ydl.extract_info(result["url"], download=False)
		except Exception as e :
			self.error(f"Error : {e}")
			self.failed = True
			return
		result["rfs"] = info["url"]
		formats = info.get("formats", [])
		video_formats = [f for f in formats if f.get("vcodec") != "none" and f.get("acodec") == "none"]
		audio_formats = [f for f in formats if f.get("acodec") != "none" and f.get("vcodec") == "none"]
		result["videos"] = {}
		for i, vid in enumerate(video_formats) :
			result["videos"][f"video{i}"] = {
						  "resolution" : vid["height"],
						  "url" : vid["url"],
						  "protocol" : vid["protocol"],
						  "fps" : vid["fps"],
						  "extension" : vid["ext"],
						  "codec" : vid["vcodec"]
			}
		result["audios"] = {}
		for i, aud in enumerate(audio_formats) :
			result["audios"][f"audio{i}"] = {
						"quality" : aud["format_note"],
						"extension" : aud["audio_ext"],
						"url" : aud["url"],
						"protocol" : aud["protocol"]
			}
		self.save()
		self.loading_animation = False
		self.thumbnail_label.configure(text = "▶️", font = ('Arial', 50), text_color = settings_config["ui"]["second_color"])
		self.thumbnail_label.bind("<Button-1>", lambda	e, url = result["rfs"] :  (os.system("pkill vlc"), subprocess.Popen(["vlc", url])))
		if not jfs :
			self.after(0, lambda : self.options_show(result))
	def options_show(self, result) :
		
		
		
		if result :
			v_extensions = []
			resolutions = []
			v_codecs = []
			fpss = []
			protocols = []
			a_qualities = []
			a_extensions = []
			
			for vid in result["videos"].values() :
				v_extensions.append(vid["extension"])
				v_codecs.append(vid["codec"][:4])
				resolutions.append(f"{vid["resolution"]}p")
				fpss.append(vid["fps"])
				protocols.append(vid["protocol"])
			for aud in result["audios"].values() :
				a_extensions.append(aud["extension"])
				a_qualities.append(aud["quality"])
		else :
			#v_extensions = self.common_formats["v_extensions"]
			#resolutions = self.common_formats["resolutions"]
			#v_codecs = self.common_formats["v_codecs"]
			#fpss = self.common_formats["fpss"]
			#protocols = self.common_formats["protocols"]
			#a_qualities = self.common_formats["a_qualities"]
			#a_extensions = self.common_formats["a_extensions"]
			pass
			
				
		global dw
		if hasattr(self, "loading") :
			self.loading.destroy()
		vora_frame = tk.CTkFrame(self.options_frame)
		vora_frame.pack(padx=5, pady=(5, 0), fill = "both")
		video_label = tk.CTkLabel(vora_frame, text="video")
		video_label.pack(padx=20, pady=5, side = "left")
		self.v_check = tk.CTkCheckBox(vora_frame, text = "")
		self.v_check.pack(padx=0, pady=5, side = "right")
		video_options_frame = tk.CTkFrame(self.options_frame)
		video_options_frame.pack(padx=5, pady=5, fill = "both")
			
		de_frame = tk.CTkFrame(video_options_frame)
		de_frame.pack(padx=5, pady=(5, 0), fill = "both")
		labelone_e = tk.CTkLabel(de_frame, text = "extension :")
		labelone_e.pack(padx=20, pady=(0, 0), fill = "both", side = "left")
		self.extension_option = tk.CTkOptionMenu(de_frame, values=[ str(r) for r in self.listing(v_extensions)])
		self.extension_option.set(self.listing(v_extensions)[0])  # default value
		self.extension_option.pack(pady=5, padx = 5, side = "right")

		dc_frame = tk.CTkFrame(video_options_frame)
		dc_frame.pack(padx=5, pady=(5, 0), fill = "both")
		labelvc = tk.CTkLabel(dc_frame, text = "codec :")
		labelvc.pack(padx=20, pady=(0, 0), fill = "both", side = "left")
		self.codec_option = tk.CTkOptionMenu(dc_frame, values=[ str(r) for r in self.listing(v_codecs)])
		self.codec_option.set(self.listing(v_codecs)[0])  # default value
		self.codec_option.pack(pady=5, padx = 5, side = "right")

		dq_frame = tk.CTkFrame(video_options_frame)
		dq_frame.pack(padx=5, pady=(5, 5), fill = "both")
		labelone = tk.CTkLabel(dq_frame, text = "quality :")
		labelone.pack(padx=20, pady=(0, 0), fill = "both", side = "left")
		self.quality_option = tk.CTkOptionMenu(dq_frame, values=[ str(r) for r in self.listing(resolutions)])
		self.quality_option.set(self.listing(resolutions)[0])  # default value
		self.quality_option.pack(pady=5, padx = 5, side = "right")

		df_frame = tk.CTkFrame(video_options_frame)
		df_frame.pack(padx=5, pady=(0, 5), fill = "both")
		labeltwo = tk.CTkLabel(df_frame, text = "frame_rate :")
		labeltwo.pack(padx=20, pady=(0, 0), fill = "both", side = "left")
		self.fps_option = tk.CTkOptionMenu(df_frame, values=[ str(int(r)) for r in self.listing(fpss)])
		self.fps_option.set(str(int(self.listing(fpss)[0])))	 # default value
		self.fps_option.pack(pady=5, padx = 5, side = "right")

		dp_frame = tk.CTkFrame(video_options_frame)
		dp_frame.pack(padx=5, pady=(0, 5), fill = "both")
		labelthree = tk.CTkLabel(dp_frame, text = "protocol :")
		labelthree.pack(padx=20, pady=(0, 0), fill = "both", side = "left")
		self.prtc_option = tk.CTkOptionMenu(dp_frame, values=self.listing(protocols))
		self.prtc_option.set(self.listing(protocols)[0])	 # default value
		self.prtc_option.pack(pady=5, padx = 5, side = "right")
		
		
		
		a_options_frame = tk.CTkFrame(dw)
		a_options_frame.pack(padx=5, pady=(0, 5), fill = "both" )
		vora_frame2 = tk.CTkFrame(a_options_frame)
		vora_frame2.pack(padx=5, pady=5, fill = "both")
		audeo_label = tk.CTkLabel(vora_frame2, text="audio")
		audeo_label.pack(padx=20, pady=5, side = "left")
		self.a_check = tk.CTkCheckBox(vora_frame2, text = "")
		self.a_check.pack(padx=0, pady=5, side = "right")
		sub_a_options_frame = tk.CTkFrame(a_options_frame)
		sub_a_options_frame.pack(padx=5, pady=(0, 5), fill = "both")
		dae_frame = tk.CTkFrame(sub_a_options_frame)
		dae_frame.pack(padx=5, pady=(5, 5), fill = "both")
		labelae = tk.CTkLabel(dae_frame, text = "extension :")
		labelae.pack(padx=20, pady=(0, 0), fill = "both", side = "left")
		self.a_extension_option = tk.CTkOptionMenu(dae_frame, values=[ str(r) for r in self.listing(a_extensions)])
		self.a_extension_option.set(str(self.listing(a_extensions)[0]))	 # default value
		self.a_extension_option.pack(pady=5, padx = 5, side = "right")
		daq_frame = tk.CTkFrame(sub_a_options_frame)
		daq_frame.pack(padx=5, pady=(0, 5), fill = "both")
		labelaq = tk.CTkLabel(daq_frame, text = "audio quality :")
		labelaq.pack(padx=20, pady=(0, 0), fill = "both", side = "left")
		self.a_quality_option = tk.CTkOptionMenu(daq_frame, values=[ str(r) for r in self.listing(a_qualities)])
		self.a_quality_option.set(str(self.listing(a_qualities)[0]))	 # default value
		self.a_quality_option.pack(pady=5, padx = 5, side = "right")
		if not self.playlist_title :
			check = tk.CTkButton(dw, text = "download", command = lambda current = result : self.getting_download(current))
		else :
			check = tk.CTkButton(dw, text = "download", command = lambda current = result : self.download_playlist)
		check.pack(padx=5, pady=5)
	   
	def save_file_native(self, filename, ext):
		file_path = None
		# 1. Initialize the GTK application (required behind the scenes)
		# We don't show a window, but we need the app context
		win = Gtk.Window(title="Save File")
	
		# 2. Create the native FileChooserDialog
		# Arguments: Title, Parent Window, Action (Save/Open)
		dialog = Gtk.FileChooserDialog(
			title="Save File", 
			parent=win, 
			action=Gtk.FileChooserAction.SAVE
			)
	
	
		# 3. Add standard buttons (Cancel and Save)
		dialog.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
		dialog.add_button(Gtk.STOCK_SAVE, Gtk.ResponseType.OK)

		# 4. Set default filename and filters
		dialog.set_current_name(f"{filename}.{ext}")
	
		filter_text = Gtk.FileFilter()
		filter_text.set_name(f"{ext.upper()} files")
		filter_text.add_pattern(f"*.{ext}")
		dialog.add_filter(filter_text)

		dialog.show_all()
		# 5. Run the dialog and wait for response
		response = dialog.run()

		if response == Gtk.ResponseType.OK:
			file_path = dialog.get_filename()
	
		# 6. Destroy the dialog to free memory
		dialog.destroy()
		win.destroy()
		del dialog
		
		while Gtk.events_pending():
			Gtk.main_iteration()
		return file_path
	
   
   
	def getting_download(self, result) :
		if hasattr(self, 'error_window') and self.error_window.winfo_exists():
			self.error_window.destroy()
		if self.v_check.get() and not self.a_check.get():
			for key, vid in result["videos"].items() :
				found = False
				if vid["codec"][:4] == self.codec_option.get() and str(vid["resolution"]) == self.quality_option.get().removesuffix("p") and vid["extension"] == self.extension_option.get() and vid["fps"] == int(self.fps_option.get()) and vid["protocol"] == self.prtc_option.get() :
						#print(f"it's {key}")
						found = True
						self.start_downloading(vid["url"], vid["extension"], f"{self.sanitize_filename(result["title"])}_VIDEO")
						break
			if not found :
				self.error("No video was found, try another combination 🙂")
				return
		elif self.a_check.get() and not self.v_check.get() :
			for key, aud in result["audios"].items() :
				found = False
				if aud["quality"] == self.a_quality_option.get() and aud["extension"] == self.a_extension_option.get() :
					#print(f"it's {key}")
					found = True
					self.start_downloading(aud["url"], aud["extension"], f"{self.sanitize_filename(result["title"])}_AUDIO")
					break
			if not found :
				self.error("No audio was found, try another combination 🙂")
				return
		elif self.v_check.get() and self.a_check.get() :
				for key, vid in result["videos"].items() :
					v_found = False
					if str(vid["resolution"]) == self.quality_option.get().removesuffix("p") and vid["extension"] == self.extension_option.get() and vid["fps"] == int(self.fps_option.get()) and vid["protocol"] == self.prtc_option.get() :
							#print(f"it's {key}")
							v_found = True
							v_url = vid["url"]
							v_ext = vid["extension"]
							break
				if not v_found :
					self.error("No video was found, try another combination 🙂")
					return
				for key, aud in result["audios"].items() :
						a_found = False
						if aud["quality"] == self.a_quality_option.get() and aud["extension"] == self.a_extension_option.get() :
							#print(f"it's {key}")
							a_found = True
							a_url = aud["url"]
							a_ext = aud["extension"]
							break
				if not a_found :
					self.error("No audio was found, try another combination 🙂")
					return
				if a_found and v_found :
					video_path = f"{self.save_file_native(result["title"], v_ext).removesuffix(f".{v_ext}")}_VIDEO.{v_ext}"
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
			video_path = self.save_file_native(title, ext)
			if video_path :
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
			save_path = self.save_file_native(title, ext)
			self.thread = threading.Thread(target=self.saving, args=(url, ext, title, self.save_path, type))
			self.thread.start()
  
	def saving(self, url, ext, title, save_path, type):
		print(url)
		if not save_path:
			return
	
		print(f"Downloading to: {save_path}")
	
		# Check if aria2c is available
		aria2c_available = shutil.which("aria2c") is not None
	
		ydl_opts = {
			'outtmpl': save_path,
			'quiet': True,
			'noplaylist': True,
			'progress': True,  # Show progress
			'continuedl': True,	 # Continue interrupted downloads
			'retries': 10,	# Retry on failure
			'fragment_retries': 10,
			'file_access_retries': 5,
		}
	
		# Use aria2c if available
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
					'--max-overall-download-limit=0',  # No limit
					'--max-download-limit=0',
					'--optimize-concurrent-downloads=true',
					'--summary-interval=0',	 # Don't spam output
					'--auto-file-renaming=false',
				]
			})
			print("Using aria2c for faster downloads...")
		else :
			print("aria2c not installed !")	 
	
		try:
			with yt_dlp.YoutubeDL(ydl_opts) as ydl:
				ydl.download([url])
			print("Download complete.")
		
			# Open folder after download
			if type not in ["video", "audio"]:
				folder = os.path.dirname(save_path)
				# Use SmartFileManager if available
				subprocess.Popen(["thunar", folder])
		
			if type == "video":
				self.v_path = save_path
			elif type == "audio":
				self.a_path = save_path
				self.merging(self.v_path, self.a_path)
				
		except Exception as e:
			self.error(f"{type} download failed - {e} - try another {type} quality !")
			return
	def merging(self, video, audio) :
		print(f"video : {video}")
		print(f"audio : {audio}")
		output_path = video.replace("_VIDEO", "")
		command = [
			"ffmpeg",
			"-loglevel", "error",
			"-i", video,
			"-i", audio,
			"-c:v", "copy",	 # copy video codec
			"-c:a", "aac",	 # encode audio to AAC
			"-strict", "experimental",
			output_path
		]

		try :
			subprocess.run(command, check=True)
			print("Merging complete.")
		except subprocess.CalledProcessError as e :
			self.error(f"error : {e}")
			
		os.remove(video)
		os.remove(audio)
		#subprocess.Popen(["thunar", os.path.dirname(output_path)])

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
		user_input = self.search.get()
		self.playlist_title = None
		self.clean_cache()
		self.search_progress = tk.CTkProgressBar(self, width=200)
		self.search_progress.pack(pady=10)
		self.search_progress.start()
		def fetching_video() :
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
					'player_client': ['android_sdkless'],  # Try different clients
					'player_skip': ['configs'],  # Skip some configs
					}
				}
			}
			try :
				with yt_dlp.YoutubeDL(ydl_opts) as ydl:
					info = ydl.extract_info(user_input, download=False)

			except Exception as e :	
				self.error(f"Error : {e}")
				self.failed = True
				return
			result["title"] = info["title"]
			result["url"] = info["url"]
			formats = info.get("formats", [])
			video_formats = [f for f in formats if f.get("vcodec") != "none" and f.get("acodec") == "none"]
			audio_formats = [f for f in formats if f.get("acodec") != "none" and f.get("vcodec") == "none"]
			result["videos"] = {}
			for i, vid in enumerate(video_formats) :
				result["videos"][f"video{i}"] = {
					"resolution" : vid["height"],
					"url" : vid["url"],
					"protocol" : vid["protocol"],
					"fps" : vid["fps"],
					"extension" : vid["ext"],
					"codec" : vid["vcodec"]
				}
			result["audios"] = {}
			for i, aud in enumerate(audio_formats) :
				result["audios"][f"audio{i}"] = {
					"quality" : aud["format_note"],
					"extension" : aud["audio_ext"],
					"url" : aud["url"],
					"protocol" : aud["protocol"]
					}

			if 'thumbnails' in info and info['thumbnails']:
				thumb_url = info['thumbnails'][settings_config["search"]["thumbnail_quality"]]['url']
			else:
				thumb_url = info.get('thumbnail')
			response = requests.get(thumb_url, timeout = 10)
			result["thumb_path"] = os.path.join(main_folder, "thumb", f"{self.sanitize_filename(result['title'])}.png")
			with open(result["thumb_path"], "wb") as f:
				f.write(response.content)
			self.search_progress.stop()
			self.search_progress.pack_forget()
			if not self.failed :
				self.after(0, lambda: self.download_window(result))
				self.save()




		def fetching_search():
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
			try :
				with yt_dlp.YoutubeDL(ydl_opts) as ydl:
					start = time.time()
					info = ydl.extract_info(query, download=False)
					print("things getted")
			except Exception as e :
				self.error(f"Error : {e}")
				self.failed = True
				return
			end = time.time()
			
			info['entries'] = [
				e for e in info['entries']
					if e.get('ie_key') != 'YoutubeTab' 
				]
  
			for i in range(len(info["entries"])) :
				self.results[f"result{i}"] = {}
			
			print(f"tooked {(end - start):.2f}s !")
			for entry, result in zip(info["entries"], self.results.values()):
					result["title"] = entry["title"]
					result["url"] = entry["url"]
					if 'thumbnails' in entry and entry['thumbnails']:
						if settings_config["search"]["thumbnail_quality"] == 0 :
							thumb_url = entry['thumbnails'][0]['url']
						else :
							thumb_url = entry['thumbnails'][len(entry['thumbnails']) - 1]['url']
					else:
						thumb_url = entry.get('thumbnail')
					print(thumb_url)
					response = requests.get(thumb_url, timeout = 10)
					result["thumb_path"] = os.path.join(main_folder, "thumb", f"{self.sanitize_filename(result['title'])}.png")
					with open(result["thumb_path"], "wb") as f:
						f.write(response.content)
					print("done for an entry")
			self.after(0, self.search_progress.stop)
			self.after(0, self.search_progress.pack_forget)
			if not self.failed :
				self.after(0, self.resultsshow)
				self.after(0, self.save)

		def fetching_playlist():
			self.results = {} 
			
			class ErrorLogger:
				def __init__(self):
					self.unavailable = 0

				def error(self, msg):
					if "Video unavailable" in msg:
						self.unavailable += 1
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
				'igoneerrors' : True,
				'logger' : logger
			}
			try :
				with yt_dlp.YoutubeDL(ydl_opts) as ydl:
					start = time.time()
					info = ydl.extract_info(user_input, download=False)
					missing_videos = logger.unavailable
					print("things getted")
			except Exception as e :
				print(e)
				self.error(f"Error : {e}")
				self.failed = True
				return
			end = time.time()
			self.playlist_title = info["title"]
			rn = info["playlist_count"] - missing_videos
			for i in range(rn) :
				self.results[f"result{i}"] = {}
			self.failed = False
			query = f"ytsearch{rn}:{user_input}"
			
			print(f"tooked {(end - start):.2f}s !")
			for entry, result in zip(info["entries"], self.results.values()):
					result["title"] = entry["title"]
					result["url"] = entry["url"]
					if 'thumbnails' in entry and entry['thumbnails']:
						thumb_url = entry['thumbnails'][settings_config["search"]["thumbnail_quality"]]['url']
					else:
						thumb_url = entry.get('thumbnail')

					response = requests.get(thumb_url, timeout = 10)
					result["thumb_path"] = os.path.join(main_folder, "thumb", f"{self.sanitize_filename(result['title'])}.png")
					with open(result["thumb_path"], "wb") as f:
						f.write(response.content)
					print("done for an entry")

			
			# Update GUI in main thread
			self.after(0, self.search_progress.stop)
			self.after(0, self.search_progress.pack_forget)
			if not self.failed :
				self.after(0, self.resultsshow)
				self.after(0, self.save)
	
		if user_input[:8] == "https://" :
			if "playlist" in  user_input :
				operation = fetching_playlist
			else :
				operation = fetching_video
		else :
			print("search")
			operation = fetching_search
		threading.Thread(target=operation).start()
	def settings(self, event) :
		thumbnail_qualities = ["low", "high"]
		def save_settings_() :
			
			error = False
			main_color = self.main_color_choice.get()
			second_color = self.second_color_choice.get()
			results_number = self.RESULTS_NUMBER_choice.get()
			thumbnail_quality = self.thumb_quality_option.get()
			
			
			def write_to_file() :
				with open(settings_config_file_path, "w") as f :
					json.dump(settings_config, f, indent = 4)
				self.destroy()
				os.execl(sys.executable, sys.executable, *sys.argv)
			
			def is_valid_color(colors):
				try:
					for color in colors:
						ImageColor.getcolor(color, "RGB")
					return True
				except ValueError:
					return False
			if (len(self.main_color_choice.get()) == 7 and self.main_color_choice.get()[:1] == "#") or is_valid_color([self.main_color_choice.get(), self.second_color_choice.get()]) :
				settings_config["ui"] = {
					"main_color" : self.main_color_choice.get(),
					"second_color" : self.second_color_choice.get()
					}
			else :
				self.main_color_choice.delete(0, "end")
				self.main_color_choice.configure(placeholder_text = "wrong choice !")
				self.second_color_choice.delete(0, "end")
				self.second_color_choice.configure(placeholder_text = "wrong choice!")
				error = True
				
			if results_number.isnumeric() :
				print("should work ?")
				settings_config["search"]["results_number"] = int(results_number)
			else :
				print("has failed")
				error = True
				self.RESULTS_NUMBER_choice.insert(0, str(settings_config["search"]["results_number"]))
			
			settings_config["search"]["thumbnail_quality"] = thumbnail_qualities.index(thumbnail_quality)
			
				
			if not error :
				write_to_file()
		def cc() :
			self.results = {}
			self.save()
			self.resultsshow()
		if hasattr(self, 'stt') and self.stt.winfo_exists():
			self.stt.destroy()
			return
		self.stt = tk.CTkToplevel(self)
		self.stt.geometry("300x550")
		self.stt.title("settings")
		self.stt.resizable(False, False)
		title_frame = tk.CTkFrame(self.stt)
		title_frame.pack(padx=5, pady=5, fill="x")
		title = tk.CTkLabel(title_frame, text ="settings", font = ('Arial', 20, "bold"), wraplength = 250)
		title.pack(padx=5, pady=5)
		
		UI_frame = tk.CTkFrame(self.stt)
		UI_frame.pack(padx=5, pady=(0, 5), fill="x")
		
		UI_title_frame = tk.CTkFrame(UI_frame)
		UI_title_frame.pack(padx=5, pady=(5, 0), fill="x")
		UI_title = tk.CTkLabel(UI_title_frame, text = "UI", font = ('Arial', 20, "bold"), wraplength = 250)
		UI_title.pack(padx=5, pady=5)
		UI_options_frame = tk.CTkFrame(UI_frame)
		UI_options_frame.pack(padx=5, pady=5, fill="x")

		main_color_frame = tk.CTkFrame(UI_options_frame)
		main_color_frame.pack(padx=5, pady=5, fill="x")
		main_color_label = tk.CTkLabel(main_color_frame, text = "main_color :")
		main_color_label.pack(padx=20, pady=5, side = "left")
		self.main_color_choice = tk.CTkEntry(main_color_frame, placeholder_text = "HEX color")
		self.main_color_choice.pack(padx=5, pady=5, side = "right")
		self.main_color_choice.insert(0, settings_config["ui"]["main_color"])

		second_color_frame = tk.CTkFrame(UI_options_frame)
		second_color_frame.pack(padx=5, pady=5, fill="x")
		second_color_label = tk.CTkLabel(second_color_frame, text="second_color :")
		second_color_label.pack(padx=20, pady=5, side="left")
		self.second_color_choice = tk.CTkEntry(second_color_frame, placeholder_text="HEX color")
		self.second_color_choice.pack(padx=5, pady=5, side="right")
		self.second_color_choice.insert(0, settings_config["ui"]["second_color"])
		

		SEARCH_frame = tk.CTkFrame(self.stt)
		SEARCH_frame.pack(padx=5, pady=(0, 5), fill="x")
		
		SEARCH_title_frame = tk.CTkFrame(SEARCH_frame)
		SEARCH_title_frame.pack(padx=5, pady=(5, 0), fill="x")
		SEARCH_title = tk.CTkLabel(SEARCH_title_frame, text = "SEARCH", font = ('Arial', 20, "bold"), wraplength = 250)
		SEARCH_title.pack(padx=5, pady=5)
		SEARCH_options_frame = tk.CTkFrame(SEARCH_frame)
		SEARCH_options_frame.pack(padx=5, pady=5, fill="x")

		RESULTS_NUMBER_frame = tk.CTkFrame(SEARCH_options_frame)
		RESULTS_NUMBER_frame.pack(padx=5, pady=5, fill="x")
		RESULTS_NUMBER_label = tk.CTkLabel(RESULTS_NUMBER_frame, text = "results number :")
		RESULTS_NUMBER_label.pack(padx=20, pady=5, side = "left")
		self.RESULTS_NUMBER_choice = tk.CTkEntry(RESULTS_NUMBER_frame, placeholder_text = "number")
		self.RESULTS_NUMBER_choice.pack(padx=5, pady=5, side = "right")
		self.RESULTS_NUMBER_choice.insert(0, str(settings_config["search"]["results_number"]))
		
		thumb_quality_frame = tk.CTkFrame(SEARCH_options_frame)
		thumb_quality_frame.pack(padx=5, pady=(5, 5), fill = "both")
		labeltq = tk.CTkLabel(thumb_quality_frame, text = "thumbnail quality :")
		labeltq.pack(padx=20, pady=(0, 0), fill = "both", side = "left")
		self.thumb_quality_option = tk.CTkOptionMenu(thumb_quality_frame, values=[ str(r) for r in thumbnail_qualities])
		self.thumb_quality_option.set(thumbnail_qualities[settings_config["search"]["thumbnail_quality"]])	 # default value
		self.thumb_quality_option.pack(pady=5, padx = 5, side = "right")
		
		last_frame = tk.CTkFrame(self.stt)
		last_frame.pack(padx=5, pady=5, fill="x", side = "bottom")
		clear_cache = tk.CTkButton(last_frame, text = "clear cache", command = cc )
		clear_cache.pack(padx=5, pady=5, side = "left")
		save_settings = tk.CTkButton(last_frame, text = "save", command = save_settings_)
		save_settings.pack(padx=5, pady=5, side = "right")
		
		


if __name__ == "__main__":
	app_instance = app()
	app_instance.mainloop()

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



