# ReadVideo API Reference

*Generated: 2025-08-26*

Comprehensive API documentation for the ReadVideo transcription tool, covering all public classes, methods, and interfaces.

## 📋 Table of Contents
- [Overview](#overview)
- [Core Classes](#core-classes)
- [Platform Handlers](#platform-handlers)
- [User Content Processing](#user-content-processing)
- [Exception Handling](#exception-handling)
- [Data Structures](#data-structures)
- [Configuration](#configuration)

---

## Overview

### Architecture Pattern
ReadVideo follows a **strategy pattern** for platform-specific processing with common interfaces and shared core services.

### Core Design Principles
1. **Subtitle Priority**: Prefer existing subtitles over audio transcription (10-100x faster)
2. **Fallback Mechanisms**: Graceful degradation when primary methods fail
3. **Tool Reuse**: Leverage existing native tools (whisper-cli, ffmpeg, yt-dlp, BBDown)
4. **Consistent Interfaces**: Common method signatures across all platform handlers

---

## Core Classes

### AudioProcessor

**Purpose**: Audio format conversion, video processing, and media file handling

#### Class Definition
```python
class AudioProcessor:
    def __init__(self, cleanup: bool = True)
```

#### Core Methods

##### `verify_ffmpeg() -> bool`
**Verifies FFmpeg availability**
```python
def verify_ffmpeg(self) -> bool:
    """Check if ffmpeg is available in the system PATH"""
```

**Returns**: `bool` - True if ffmpeg is available, False otherwise  
**Raises**: None (graceful failure detection)

##### `get_file_info(file_path: str) -> Dict[str, Any]`
**Extracts metadata from media files**
```python
def get_file_info(self, file_path: str) -> Dict[str, Any]:
    """Get file information including format, duration, and codec details"""
```

**Parameters**:
- `file_path` (str): Path to the media file

**Returns**: 
```python
{
    "format": str,           # File format (mp4, mkv, mp3, etc.)
    "duration": float,       # Duration in seconds
    "size": int,            # File size in bytes
    "audio_codec": str,     # Audio codec (aac, mp3, etc.)
    "video_codec": str,     # Video codec (h264, etc.) - if applicable
    "sample_rate": int,     # Audio sample rate
    "channels": int         # Audio channel count
}
```

**Raises**: `AudioProcessingError` if file cannot be processed

##### `extract_audio_from_video(video_path: str, output_path: str) -> str`
**Extracts audio track from video files**
```python
def extract_audio_from_video(self, video_path: str, output_path: str) -> str:
    """Extract audio from video file and save as WAV"""
```

**Parameters**:
- `video_path` (str): Input video file path
- `output_path` (str): Output audio file path

**Returns**: `str` - Path to extracted audio file  
**Raises**: `AudioProcessingError` if extraction fails

##### `convert_audio_format(input_path: str, output_path: str, target_format: str = "wav") -> str`
**Converts audio between formats**
```python
def convert_audio_format(self, input_path: str, output_path: str, 
                        target_format: str = "wav") -> str:
    """Convert audio file to target format"""
```

**Parameters**:
- `input_path` (str): Source audio file
- `output_path` (str): Destination file path  
- `target_format` (str): Target format ("wav", "mp3", "m4a")

**Returns**: `str` - Path to converted file  
**Supported Formats**: MP3, M4A, WAV, FLAC, OGG, AAC, WMA

##### `process_media_file(file_path: str, output_dir: str = ".") -> str`
**One-stop processing for any media file**
```python
def process_media_file(self, file_path: str, output_dir: str = ".") -> str:
    """Process any media file and prepare WAV for transcription"""
```

**Parameters**:
- `file_path` (str): Input media file (audio or video)
- `output_dir` (str): Directory for processed output

**Returns**: `str` - Path to WAV file ready for transcription  
**Processing Flow**:
1. Detect file type (audio/video)
2. Extract audio if video file
3. Convert to WAV format
4. Validate for transcription compatibility

#### Class Properties
```python
supported_audio_formats: Set[str] = {
    'mp3', 'm4a', 'wav', 'flac', 'ogg', 'aac', 'wma'
}

supported_video_formats: Set[str] = {
    'mp4', 'mkv', 'avi', 'mov', 'wmv', 'flv', 'webm', 'm4v'
}
```

---

### WhisperWrapper

**Purpose**: Interface to whisper-cli for speech-to-text transcription

#### Class Definition
```python
class WhisperWrapper:
    def __init__(self, model_path: str = "~/.whisper-models/ggml-large-v3.bin")
```

#### Core Methods

##### `transcribe(audio_file: str, language: str = None) -> str`
**Transcribes audio file to text**
```python
def transcribe(self, audio_file: str, language: str = None) -> str:
    """Transcribe audio file using whisper-cli"""
```

**Parameters**:
- `audio_file` (str): Path to WAV audio file
- `language` (str, optional): Language code ("zh", "en", "auto")

**Returns**: `str` - Transcribed text content  
**Performance**: ~0.1-0.5x audio length depending on model and hardware

##### `is_available() -> bool`
**Checks whisper-cli availability**
```python
def is_available(self) -> bool:
    """Check if whisper-cli is installed and accessible"""
```

**Returns**: `bool` - True if whisper-cli is available

---

### TranscriptFetcher

**Purpose**: YouTube subtitle extraction with language prioritization

#### Class Definition
```python
class TranscriptFetcher:
    def __init__(self)
```

#### Core Methods

##### `fetch_transcript(video_id: str, language: str = None) -> str`
**Fetches YouTube video subtitles**
```python
def fetch_transcript(self, video_id: str, language: str = None) -> str:
    """Fetch transcript from YouTube with language preference"""
```

**Parameters**:
- `video_id` (str): YouTube video ID (extracted from URL)
- `language` (str, optional): Preferred language code

**Returns**: `str` - Subtitle text content  
**Language Priority**: Chinese (zh, zh-Hans, zh-Hant) → English → Available languages

##### `get_available_transcripts(video_id: str) -> List[str]`
**Lists available subtitle languages**
```python
def get_available_transcripts(self, video_id: str) -> List[str]:
    """Get list of available transcript languages for video"""
```

**Returns**: `List[str]` - List of available language codes

---

## Platform Handlers

All platform handlers implement a common interface for consistent usage across different video sources.

### Common Interface

```python
class PlatformHandler:
    def __init__(self, whisper_model_path: str = "~/.whisper-models/ggml-large-v3.bin"): pass
    def validate_url(self, url: str) -> bool: pass
    def process(self, url: str, output_dir: str = ".", **options) -> Dict[str, Any]: pass
    def get_info(self, url: str) -> Dict[str, Any]: pass  # Note: some handlers call this get_video_info
```

---

### YouTubeHandler

**Purpose**: YouTube video processing with subtitle priority and audio fallback

#### Class Definition
```python
class YouTubeHandler:
    def __init__(self, whisper_model_path: str = "~/.whisper-models/ggml-large-v3.bin",
                 prefer_cookies: bool = False, proxy: str = None)
```

#### Constructor Parameters
- `whisper_model_path` (str): Path to Whisper model file
- `prefer_cookies` (bool): Use browser cookies for yt-dlp downloads
- `proxy` (str, optional): HTTP proxy for requests

#### Core Methods

##### `validate_url(url: str) -> bool`
**Validates YouTube URL formats**
```python
def validate_url(self, url: str) -> bool:
    """Check if URL is a valid YouTube video URL"""
```

**Supported Formats**:
- `https://www.youtube.com/watch?v=VIDEO_ID`
- `https://youtu.be/VIDEO_ID`
- `https://m.youtube.com/watch?v=VIDEO_ID`
- `https://www.youtube.com/embed/VIDEO_ID`

##### `process(url: str, output_dir: str = ".", **options) -> Dict[str, Any]`
**Main processing method with intelligent routing**
```python
def process(self, url: str, output_dir: str = ".", 
           auto_detect: bool = False, verbose: bool = False,
           no_cleanup: bool = False) -> Dict[str, Any]:
    """Process YouTube video with subtitle priority"""
```

**Processing Strategy**:
1. **Subtitle Priority**: Attempt `youtube-transcript-api` extraction
2. **Audio Fallback**: Download audio with `yt-dlp` if no subtitles
3. **Transcription**: Use Whisper for audio-to-text conversion

**Parameters**:
- `url` (str): YouTube video URL
- `output_dir` (str): Output directory for transcript
- `auto_detect` (bool): Enable automatic language detection
- `verbose` (bool): Detailed progress output
- `no_cleanup` (bool): Preserve temporary files

**Returns**: [Processing Result Format](#processing-result-format)

##### `get_video_info(url: str) -> Dict[str, Any]`
**Extracts video metadata**
```python
def get_video_info(self, url: str) -> Dict[str, Any]:
    """Get YouTube video information without processing"""
```

**Returns**:
```python
{
    "video_id": str,
    "title": str,
    "duration": str,        # Format: "10:30"
    "upload_date": str,     # Format: "2024-01-01"
    "uploader": str,
    "view_count": int,
    "description": str,
    "thumbnail": str,       # URL to thumbnail image
    "available_subtitles": List[str],  # Language codes
    "platform": "youtube"
}
```

#### Private Methods
- `_process_with_transcript()` - Handle subtitle-based processing
- `_process_with_audio_transcription()` - Handle audio-based processing
- `_download_audio()` - Download audio using yt-dlp
- `_convert_to_wav()` - Convert audio for Whisper compatibility
- `_get_video_title()` - Extract video title for filename generation
- `_sanitize_filename()` - Clean filenames for filesystem compatibility

---

### BilibiliHandler

**Purpose**: Bilibili video processing via BBDown and yt-dlp with intelligent tool selection

#### Class Definition
```python
class BilibiliHandler:
    def __init__(self, whisper_model_path: str = "~/.whisper-models/ggml-large-v3.bin",
                 proxy: str = None)
```

#### Constructor Parameters
- `whisper_model_path` (str): Path to Whisper model file
- `proxy` (str, optional): HTTP proxy for downloads

#### Core Methods

##### `validate_url(url: str) -> bool`
**Validates Bilibili URL formats**
```python
def validate_url(self, url: str) -> bool:
    """Check if URL is a valid Bilibili video URL"""
```

**Supported Formats**:
- `https://www.bilibili.com/video/BV*`
- `https://bilibili.com/video/BV*`
- `https://b23.tv/*` (short URLs)

##### `process(url: str, output_dir: str = ".", **options) -> Dict[str, Any]`
**Main processing with dual-tool strategy**
```python
def process(self, url: str, output_dir: str = ".", 
           auto_detect: bool = False, verbose: bool = False,
           no_cleanup: bool = False) -> Dict[str, Any]:
    """Process Bilibili video with BBDown/yt-dlp fallback"""
```

**Processing Strategy**:
1. **Primary**: BBDown for optimal Bilibili support
2. **Fallback**: yt-dlp if BBDown fails or unavailable
3. **Audio Processing**: Convert to WAV and transcribe

**Tool Selection Logic**:
- BBDown available + Chinese content → Use BBDown
- BBDown unavailable OR BBDown fails → Use yt-dlp
- Both fail → Return error with guidance

##### `extract_bv_id(url: str) -> str`
**Extracts Bilibili video identifier**
```python
def extract_bv_id(self, url: str) -> str:
    """Extract BV ID from various Bilibili URL formats"""
```

**Returns**: `str` - BV identifier (e.g., "BV1234567890")

##### `get_video_info(url: str) -> Dict[str, Any]`
**Extracts Bilibili video metadata**
```python
def get_video_info(self, url: str) -> Dict[str, Any]:
    """Get Bilibili video information"""
```

**Returns**:
```python
{
    "bv_id": str,
    "title": str,
    "duration": str,
    "upload_date": str,
    "uploader": str,
    "view_count": int,
    "description": str,
    "platform": "bilibili"
}
```

#### Private Methods
- `_download_with_bbdown()` - BBDown-based audio extraction
- `_download_with_ytdlp()` - yt-dlp-based audio extraction  
- `_find_audio_candidates()` - Locate downloaded audio files
- `_select_best_audio_file()` - Choose optimal audio quality
- `_cleanup_bbdown_residuals()` - Clean up BBDown temporary files
- `_convert_to_wav()` - Convert audio for transcription

---

### LocalHandler

**Purpose**: Local media file processing for audio and video files

#### Class Definition
```python
class LocalHandler:
    def __init__(self, whisper_model_path: str = "~/.whisper-models/ggml-large-v3.bin")
```

#### Core Methods

##### `validate_url(path: str) -> bool`
**Validates local file path and format**
```python
def validate_url(self, path: str) -> bool:
    """Check if path is a valid local media file"""
```

**Supported Formats**: All formats from `AudioProcessor` supported lists

##### `process(path: str, output_dir: str = ".", **options) -> Dict[str, Any]`
**Process local media files**
```python
def process(self, path: str, output_dir: str = ".", 
           auto_detect: bool = False, verbose: bool = False,
           no_cleanup: bool = False) -> Dict[str, Any]:
    """Process local audio/video file"""
```

**Processing Flow**:
1. Validate file exists and is supported format
2. Use `AudioProcessor` to prepare WAV file
3. Transcribe with Whisper
4. Generate output transcript

---

## User Content Processing

Batch processing classes for handling multiple videos from users/channels.

### BilibiliUserHandler

**Purpose**: Batch processing for all videos from a Bilibili user/channel

#### Class Definition
```python
class BilibiliUserHandler:
    def __init__(self, whisper_model_path: str = "~/.whisper-models/ggml-large-v3.bin")
```

#### Core Methods

##### `extract_uid(user_input: str) -> int`
**Extracts Bilibili user ID**
```python
def extract_uid(self, user_input: str) -> int:
    """Extract UID from Bilibili user input"""
```

**Supported Formats**:
- Direct UID: `123456`
- User space URL: `https://space.bilibili.com/123456`

##### `get_user_videos(uid: int, start_date: str = None, max_videos: int = None) -> List[Dict[str, Any]]`
**Retrieves user's video list with filtering**
```python
def get_user_videos(self, uid: int, start_date: str = None, 
                   max_videos: int = None) -> List[Dict[str, Any]]:
    """Get filtered list of user's videos"""
```

**Parameters**:
- `uid` (int): Bilibili user ID
- `start_date` (str, optional): Filter videos from date (YYYY-MM-DD)
- `max_videos` (int, optional): Maximum videos to retrieve

**Returns**: List of video information dictionaries

##### `process_user(user_input: str, output_dir: str, **options) -> Dict[str, Any]`
**Main batch processing method**
```python
def process_user(self, user_input: str, output_dir: str,
                start_date: str = None, max_videos: int = None,
                verbose: bool = False) -> Dict[str, Any]:
    """Process all videos from Bilibili user"""
```

**Features**:
- **Progress Tracking**: Real-time processing status
- **Resume Capability**: Skip already processed videos
- **Error Isolation**: Continue processing if individual videos fail
- **Comprehensive Reporting**: Detailed success/failure statistics

**Output Structure**:
```
{output_dir}/
└── {username}_{uid}/
    ├── video_list.json          # Complete video metadata
    ├── processing_status.json    # Processing state for resume
    ├── user_summary.json        # Final processing report
    └── transcripts/             # Individual video transcripts
        ├── BV1xxx_title.txt
        └── BV1yyy_title.txt
```

---

### YouTubeUserHandler

**Purpose**: YouTube channel batch processing via yt-dlp

#### Class Definition
```python
class YouTubeUserHandler:
    def __init__(self, whisper_model_path: str = "~/.whisper-models/ggml-large-v3.bin")
```

#### Core Methods

##### `extract_channel_info(channel_input: str) -> Dict[str, str]`
**Parses YouTube channel identifier**
```python
def extract_channel_info(self, channel_input: str) -> Dict[str, str]:
    """Extract channel information from various input formats"""
```

**Supported Formats**:
- `@username`
- `https://www.youtube.com/@username`
- `https://www.youtube.com/channel/UCxxx`

##### `get_channel_videos(channel_url: str, max_videos: int = None) -> List[Dict[str, Any]]`
**Retrieves channel video list via yt-dlp**
```python
def get_channel_videos(self, channel_url: str, 
                      max_videos: int = None) -> List[Dict[str, Any]]:
    """Get channel videos using yt-dlp playlist extraction"""
```

##### `process_channel(channel_input: str, output_dir: str, **options) -> Dict[str, Any]`
**Main batch processing for YouTube channels**
```python
def process_channel(self, channel_input: str, output_dir: str,
                   start_date: str = None, max_videos: int = None,
                   verbose: bool = False) -> Dict[str, Any]:
    """Process all videos from YouTube channel"""
```

**Features**: Similar to BilibiliUserHandler with YouTube-specific adaptations

---

## Exception Handling

### Exception Hierarchy

#### AudioProcessingError
```python
class AudioProcessingError(Exception):
    """Raised when audio processing operations fail"""
```

**Common Causes**:
- FFmpeg not available
- Unsupported audio format
- File corruption or access issues
- Insufficient disk space

#### TranscriptError  
```python
class TranscriptError(Exception):
    """Raised when transcript/subtitle operations fail"""
```

**Common Causes**:
- YouTube transcript API limitations
- Network connectivity issues
- Video has no available subtitles
- Invalid video ID

#### PlatformError
```python
class PlatformError(Exception):
    """Raised for platform-specific processing failures"""
```

**Common Causes**:
- Platform tool unavailable (BBDown, yt-dlp)
- Network restrictions or IP blocks
- Invalid URLs or video IDs
- Private or restricted content

#### ValidationError
```python
class ValidationError(Exception):
    """Raised for input validation failures"""
```

**Common Causes**:
- Invalid file formats
- Malformed URLs
- Missing required parameters
- File access permissions

### Error Handling Patterns

#### Graceful Degradation
```python
try:
    # Primary method (fast)
    result = fetch_subtitles(video_id)
except TranscriptError:
    # Fallback method (slower but reliable)
    result = transcribe_audio(video_url)
```

#### Resource Cleanup
```python
try:
    result = process_video(url)
except Exception as e:
    cleanup_temp_files()
    raise
finally:
    cleanup_temp_files()  # Always cleanup
```

---

## Data Structures

### Processing Result Format

All processing methods return a standardized result dictionary:

```python
{
    "success": bool,
    "input_info": {
        "url": str,                    # Original input URL/path
        "title": str,                  # Video/file title
        "duration": str,               # Duration in MM:SS format
        "platform": str,               # "youtube", "bilibili", "local"
        "file_size": int,              # File size in bytes (if applicable)
        "format": str                  # Original format
    },
    "processing_info": {
        "method": str,                 # "subtitle" | "transcription" | "local"
        "language": str,               # Detected or specified language
        "model_used": str,             # Whisper model path (if used)
        "processing_time": float,      # Total processing time in seconds
        "temp_files_created": List[str] # Temporary files (if no_cleanup=True)
    },
    "output": {
        "file": str,                   # Path to output transcript file
        "content_preview": str,        # First 200 characters of content
        "word_count": int,             # Approximate word count
        "character_count": int,        # Character count including spaces
        "estimated_reading_time": str   # Estimated reading time
    },
    "error": Optional[str],            # Error message if success=False
    "warnings": List[str]              # Non-fatal warnings
}
```

### Batch Processing Result Format

User/channel processing returns extended result information:

```python
{
    "user_info": {
        "uid": int,                    # User/channel identifier
        "username": str,               # Display name
        "total_videos": int,           # Total videos available
        "follower_count": int,         # Followers/subscribers (if available)
        "platform": str                # "bilibili" | "youtube"
    },
    "processing_stats": {
        "videos_requested": int,       # Number of videos to process
        "videos_processed": int,       # Successfully processed
        "videos_failed": int,          # Failed processing
        "videos_skipped": int,         # Already existed or filtered out
        "total_duration": str,         # Combined duration (HH:MM:SS)
        "total_text_length": int,      # Combined character count
        "processing_time": str,        # Total processing time
        "start_time": str,             # ISO timestamp
        "end_time": str                # ISO timestamp
    },
    "video_results": List[Dict],       # Individual video results
    "failed_videos": List[Dict],       # Failed video information
    "output_directory": str            # Base output directory
}
```

### Configuration Structure

Configuration options for all handlers:

```python
{
    "whisper_model_path": str,         # Path to Whisper model
    "output_dir": str,                 # Default output directory
    "auto_detect": bool,               # Automatic language detection
    "prefer_cookies": bool,            # Use browser cookies for downloads
    "proxy": Optional[str],            # HTTP proxy configuration
    "verbose": bool,                   # Detailed logging
    "no_cleanup": bool,                # Preserve temporary files
    "max_retries": int,                # Network retry attempts
    "retry_delay": float               # Delay between retries
}
```

---

## Configuration

### Default Paths and Values

```python
DEFAULT_WHISPER_MODEL = "~/.whisper-models/ggml-large-v3.bin"
DEFAULT_OUTPUT_DIR = "."
DEFAULT_LANGUAGE = "zh"  # Chinese
SUPPORTED_AUDIO_FORMATS = {'mp3', 'm4a', 'wav', 'flac', 'ogg', 'aac', 'wma'}
SUPPORTED_VIDEO_FORMATS = {'mp4', 'mkv', 'avi', 'mov', 'wmv', 'flv', 'webm', 'm4v'}
```

### Environment Variables

```bash
READVIDEO_WHISPER_MODEL=/path/to/model.bin    # Override default model path
READVIDEO_OUTPUT_DIR=/path/to/output          # Override default output directory  
READVIDEO_PROXY=http://127.0.0.1:8080        # Default proxy configuration
```

### Dependency Requirements

#### Required System Tools
- **ffmpeg**: Audio/video processing - `brew install ffmpeg` or `apt install ffmpeg`
- **whisper-cli**: Speech transcription - Install whisper.cpp

#### Optional System Tools  
- **BBDown**: Bilibili video extraction - Enhanced Bilibili support
- **yt-dlp**: Already included as Python dependency

#### Python Dependencies
See [`pyproject.toml`](../pyproject.toml) for complete dependency specifications

---

*This API reference provides comprehensive documentation for all public interfaces in the ReadVideo project. Each class and method includes usage examples, parameter specifications, return value formats, and error handling information.*

**Generated by**: Claude Code SuperClaude Framework  
**Last Updated**: 2025-08-26  
**Version**: ReadVideo 0.1.1