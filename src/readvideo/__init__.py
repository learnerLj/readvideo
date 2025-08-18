"""ReadVideo - Video and Audio Transcription Tool.

A Python tool for downloading and transcribing videos from YouTube/Bilibili
and local media files, with transcript priority for YouTube videos.
"""

__version__ = "0.1.0"
__author__ = "Jiahao Luo"
__email__ = "luoshitou9@gmail.com"

# Don't import CLI module during package initialization to avoid
# "found in sys.modules" warning when running as module
__all__: list[str] = []
