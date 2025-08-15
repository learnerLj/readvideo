"""ReadVideo - Video and Audio Transcription Tool.

A Python tool for downloading and transcribing videos from YouTube/Bilibili 
and local media files, with transcript priority for YouTube videos.
"""

__version__ = "0.1.0"
__author__ = "Jiahao Luo"
__email__ = "luoshitou9@gmail.com"

from .cli import main

__all__ = ["main"]
