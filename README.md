# yt-dlp GUI

A modern, lightweight GUI application for downloading YouTube videos using `yt-dlp`, built with CustomTkinter.

## Features ✨

- **Fast Downloads**: Uses aria2c for accelerated parallel downloading (when available)
- **Smart Caching**: Caches video info and thumbnails for faster browsing
- **Multiple Format Support**: Choose from various video qualities, codecs, and frame rates
- **Search & Browse**: Search YouTube directly or paste URLs
- **Watch Instantly**: Stream videos directly in VLC player
- **Customizable UI**: Choose your preferred color theme
- **Cross-Platform**: Works on Linux, Windows, and macOS
- **Thumbnail Previews**: See video thumbnails in search results

## Installation 📦

### Prerequisites
- Python 3.7 or higher
- ffmpeg (for video/audio merging)
- VLC (for instant playback, optional)
- aria2c (for faster downloads, optional but recommended)

### 1. Install from source

```bash
# Clone the repository
git clone https://github.com/yourusername/yt-dlp-gui.git
cd yt-dlp-gui

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
