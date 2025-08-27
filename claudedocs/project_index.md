# ReadVideo Project Index

*Generated: 2025-08-26*

A comprehensive cross-referenced index of the ReadVideo project - a modern Python-based video transcription tool supporting YouTube, Bilibili, and local media files.

## 📋 Table of Contents
- [Project Overview](#project-overview)
- [Core Architecture](#core-architecture)
- [Module Index](#module-index)
- [API Reference](#api-reference)
- [Command Line Interface](#command-line-interface)
- [Configuration & Setup](#configuration--setup)
- [Development Workflow](#development-workflow)
- [Cross-References](#cross-references)

---

## Project Overview

### 🎯 Purpose
ReadVideo extracts and transcribes content from multiple sources with intelligent subtitle prioritization and fallback mechanisms.

### 🏗️ Architecture Pattern
- **Layered Architecture**: CLI → Platform Handlers → Core Services → External Tools
- **Strategy Pattern**: Platform-specific processing strategies
- **Template Method**: Common processing workflows with platform variations

### 📊 Project Statistics
- **Language**: Python 3.11+
- **Package Structure**: 23 Python files across 6 modules
- **External Dependencies**: 11 core packages
- **Platform Support**: 3 platforms (YouTube, Bilibili, Local)
- **CLI Commands**: 5 primary commands

---

## Core Architecture

### 📦 Package Structure
```
src/readvideo/
├── __init__.py              # Package initialization
├── __main__.py              # Entry point for python -m readvideo
├── cli.py                   # [CLI] Main command-line interface
├── core/                    # [CORE] Core processing services
│   ├── __init__.py
│   ├── audio_processor.py   # AudioProcessor class
│   ├── transcript_fetcher.py # YouTube subtitle fetcher
│   ├── whisper_wrapper.py   # whisper-cli interface
│   └── supadata_fetcher.py  # Supadata API integration
├── platforms/               # [PLATFORMS] Platform-specific handlers
│   ├── __init__.py
│   ├── youtube.py           # YouTubeHandler class
│   ├── bilibili.py          # BilibiliHandler class  
│   └── local.py             # LocalHandler class
├── user_content/            # [USER] Batch processing for user content
│   ├── __init__.py
│   ├── bilibili_user.py     # Bilibili user/channel processing
│   ├── youtube_user.py      # YouTube channel processing
│   ├── utils.py             # User content utilities
│   ├── design.md            # Bilibili user design document
│   ├── youtube_design.md    # YouTube user design document  
│   └── twitter/             # Twitter content handling
│       ├── __init__.py
│       ├── twitter_handler.py
│       ├── rss_fetcher.py
│       └── utils.py
└── utils/                   # [UTILS] Shared utilities
    └── __init__.py
```

### 🔄 Data Flow Overview
1. **Input Processing**: URL detection and platform routing
2. **Content Acquisition**: Platform-specific content extraction
3. **Subtitle Priority**: Attempt subtitle extraction before audio processing  
4. **Fallback Processing**: Audio extraction and transcription via Whisper
5. **Output Generation**: Formatted transcript files

---

## Module Index

### 🎛️ CLI Module (`cli.py`)
**Primary Entry Point** - Command-line interface and user interaction

#### Key Functions
- `cli()` - Main Click CLI group → *Entry point for all commands*
- `main()` - Single file/URL processing → *Core processing workflow*  
- `user_command()` - Batch user content processing → *Bilibili user handling*
- `youtube_channel_command()` - YouTube channel processing → *Channel batch processing*
- `twitter_command()` - Twitter content processing → *Social media integration*

#### Cross-References
- → [`platforms/youtube.py`](#youtube-platform-youtubepy) for YouTube processing
- → [`platforms/bilibili.py`](#bilibili-platform-bilibilippy) for Bilibili processing
- → [`user_content/bilibili_user.py`](#bilibili-user-processing-bilibili_userpy) for user batch processing

---

### ⚙️ Core Services (`core/`)

#### Audio Processing (`audio_processor.py`)
**Audio Conversion and Format Handling**

```python
class AudioProcessor:
    def __init__(self, cleanup: bool = True)
    def extract_audio(self, input_path: str, output_path: str) -> str
    def is_audio_file(self, file_path: str) -> bool
    def is_video_file(self, file_path: str) -> bool
```

**Supported Formats**:
- Audio: MP3, M4A, WAV, FLAC, OGG, AAC, WMA
- Video: MP4, MKV, AVI, MOV, WMV, FLV, WEBM, M4V

#### Transcript Fetching (`transcript_fetcher.py`) 
**YouTube Subtitle Extraction with Language Priority**

```python
class TranscriptFetcher:
    def fetch_transcript(self, video_id: str, language: str = None) -> str
    def get_available_transcripts(self, video_id: str) -> List[str]
```

**Language Priority**: Chinese (zh, zh-Hans, zh-Hant) → English → Other

#### Whisper Integration (`whisper_wrapper.py`)
**Interface to whisper-cli for Audio Transcription**

```python  
class WhisperWrapper:
    def __init__(self, model_path: str = "~/.whisper-models/ggml-large-v3.bin")
    def transcribe(self, audio_file: str, language: str = None) -> str
    def is_available(self) -> bool
```

**Cross-References**:
- ← Used by all platform handlers in [`platforms/`](#platform-handlers-platforms)
- ← Configuration from [`pyproject.toml`](#configuration-pyprojecttoml)

---

### 🌐 Platform Handlers (`platforms/`)

#### YouTube Platform (`youtube.py`)
**YouTube Video Processing with Subtitle Priority**

```python
class YouTubeHandler:
    def __init__(self, whisper_model_path: str)
    def validate_url(self, url: str) -> bool
    def process(self, url: str, output_dir: str = ".", **options) -> Dict[str, Any]
    def get_info(self, url: str) -> Dict[str, Any]
```

**Processing Flow**:
1. Extract video ID from URL variants
2. Attempt subtitle fetching via `youtube-transcript-api` 
3. Fallback to audio download via `yt-dlp`
4. Audio transcription via Whisper

#### Bilibili Platform (`bilibili.py`)
**Bilibili Video Processing via BBDown**

```python
class BilibiliHandler:
    def __init__(self, whisper_model_path: str)  
    def validate_url(self, url: str) -> bool
    def process(self, url: str, output_dir: str = ".", **options) -> Dict[str, Any]
    def get_info(self, url: str) -> Dict[str, Any]
```

**Dependencies**: BBDown tool for Bilibili audio extraction

#### Local File Handler (`local.py`)
**Local Media File Processing**

```python
class LocalHandler:
    def __init__(self, whisper_model_path: str)
    def validate_url(self, path: str) -> bool  
    def process(self, path: str, output_dir: str = ".", **options) -> Dict[str, Any]
    def get_info(self, path: str) -> Dict[str, Any]
```

**Cross-References**:
- → [`core/audio_processor.py`](#audio-processing-audio_processorpy) for audio extraction
- → [`core/whisper_wrapper.py`](#whisper-integration-whisper_wrapperpy) for transcription
- ← Called from [`cli.py`](#cli-module-clipy) command handlers

---

### 👥 User Content Processing (`user_content/`)

#### Bilibili User Processing (`bilibili_user.py`)
**Batch Processing for Bilibili User/Channel Content**

```python
class BilibiliUserHandler:
    def __init__(self, whisper_model_path: str)
    def extract_uid(self, user_input: str) -> int
    def get_user_videos(self, uid: int, start_date=None, max_videos=None) -> List[Dict]
    def process_user(self, user_input: str, output_dir: str, **options) -> Dict[str, Any]
```

**Features**:
- UID extraction from URLs or direct input
- Date filtering and video count limits
- Batch processing with progress tracking
- Resume capability via status files

#### YouTube User Processing (`youtube_user.py`)
**YouTube Channel Batch Processing**

```python
class YouTubeUserHandler:
    def __init__(self, whisper_model_path: str)
    def extract_channel_info(self, channel_input: str) -> Dict[str, str]
    def get_channel_videos(self, channel_url: str, max_videos: Optional[int]) -> List[Dict]
    def process_channel(self, channel_input: str, output_dir: str, **options) -> Dict[str, Any]
```

**Supported Formats**:
- `@username` URLs 
- `https://www.youtube.com/@username`
- `https://www.youtube.com/channel/UCxxx`

#### Design Documentation
- [`design.md`](src/readvideo/user_content/design.md) - Bilibili user processing design
- [`youtube_design.md`](src/readvideo/user_content/youtube_design.md) - YouTube channel processing design

**Cross-References**:
- → [`platforms/bilibili.py`](#bilibili-platform-bilibilippy) for individual video processing
- → [`platforms/youtube.py`](#youtube-platform-youtubepy) for individual video processing
- ← Called from [`cli.py`](#cli-module-clipy) user commands

---

## API Reference

### Core Classes

#### Platform Handler Interface
All platform handlers implement this common interface:

```python
class PlatformHandler:
    def __init__(self, whisper_model_path: str): pass
    def validate_url(self, url: str) -> bool: pass
    def process(self, url: str, output_dir: str = ".", **options) -> Dict[str, Any]: pass  
    def get_info(self, url: str) -> Dict[str, Any]: pass
```

#### Processing Result Format
```python
{
    "success": bool,
    "input_info": {
        "url": str,
        "title": str, 
        "duration": str,
        "platform": str
    },
    "processing_info": {
        "method": str,  # "subtitle" | "transcription"
        "language": str,
        "model_used": str
    },
    "output": {
        "file": str,
        "content_preview": str,
        "word_count": int
    },
    "error": Optional[str]
}
```

### Exception Hierarchy
```python
ReadVideoError(Exception)           # Base exception with error codes
├── ValidationError(ReadVideoError)  # Input validation failures
├── NetworkError(ReadVideoError)     # Network-related failures  
├── ProcessingError(ReadVideoError)  # Processing failures (audio, transcription)
└── Backward compatibility aliases:
    ├── AudioProcessingError = ProcessingError
    ├── TranscriptFetchError = NetworkError
    └── Others...
```

---

## Command Line Interface

### Main Commands

#### `readvideo <input>`
**Single File/URL Processing**
```bash
readvideo "https://www.youtube.com/watch?v=abc123"
readvideo ~/video.mp4
```

**Options**:
- `--auto-detect` - Enable automatic language detection
- `--output-dir, -o PATH` - Output directory  
- `--no-cleanup` - Keep temporary files
- `--info-only` - Show info without processing
- `--whisper-model PATH` - Custom Whisper model path
- `--verbose, -v` - Verbose output
- `--proxy TEXT` - HTTP proxy address

#### `readvideo user <uid_or_url>`
**Bilibili User Batch Processing**
```bash
readvideo user 123456 -o ./output --start-date 2024-01-01 --max-videos 50
readvideo user https://space.bilibili.com/123456
```

#### `readvideo youtube-channel <channel>`  
**YouTube Channel Batch Processing**
```bash
readvideo youtube-channel @username -o ./output --max-videos 30
readvideo youtube-channel https://www.youtube.com/@username
```

#### `readvideo twitter <username>`
**Twitter Content Processing** 
```bash
readvideo twitter @username -o ./output --max-posts 100
```

**Cross-References**:
- → [Configuration](#configuration--setup) for setup requirements
- → [Development Workflow](#development-workflow) for testing commands

---

## Configuration & Setup

### Configuration (`pyproject.toml`)
**Project Metadata and Dependencies**

#### Core Dependencies
```toml
dependencies = [
    "youtube-transcript-api>=0.6.0",  # YouTube subtitle extraction
    "yt-dlp>=2023.12.30",             # YouTube video downloading  
    "click>=8.1.0",                   # CLI framework
    "rich>=13.0.0",                   # Console output
    "browser-cookie3>=0.19.0",        # Browser cookie extraction
    "tenacity>=8.2.0",                # Retry mechanisms
    "bilibili-api-python>=17.0.0",    # Bilibili API integration
    "httpx>=0.28.1",                  # HTTP client
    "curl-cffi>=0.13.0",              # HTTP with TLS fingerprinting
    "defusedxml>=0.7.1",              # Secure XML parsing
    "ffmpeg-python>=0.2.0",           # FFmpeg Python bindings
]
```

#### Development Dependencies
```toml
[dependency-groups]
dev = [
    "flake8>=7.3.0",                  # Code linting
    "mypy>=1.17.1",                   # Type checking
    "types-defusedxml>=0.7.0.20250822",
    "types-requests>=2.32.4.20250809",
]
```

### System Dependencies
**External Tools Required**
- `ffmpeg` - Audio/video processing
- `whisper-cli` - Speech transcription (from whisper.cpp)
- `BBDown` - Bilibili video extraction (optional)

### Installation Methods
```bash
# Global tool installation (recommended)
uv tool install readvideo
pipx install readvideo

# Development installation
git clone https://github.com/learnerLj/readvideo.git
cd readvideo && uv sync
```

**Cross-References**:
- → [README.md](README.md) for detailed installation instructions
- → [Development Workflow](#development-workflow) for development setup

---

## Development Workflow

### Project Structure
```bash
readvideo/
├── pyproject.toml          # Project configuration
├── README.md              # User documentation  
├── LICENSE                # MIT license
├── uv.lock               # Dependency lock file
├── .gitignore            # Git ignore patterns
├── src/readvideo/        # Main package source
├── test/                 # Test directory (empty)
└── claudedocs/           # Generated documentation
    ├── project_index.md  # This index document
    └── system_architecture_analysis.md
```

### Development Commands
```bash
# Code quality
flake8 src/                # Linting
mypy src/                  # Type checking

# Testing
python -m readvideo --info-only "test_input"
readvideo --help

# Package building  
uv build
```

### Adding New Platforms
1. **Create handler** in `platforms/new_platform.py`
2. **Implement interface**: `validate_url()`, `process()`, `get_info()` 
3. **Add CLI integration** in `cli.py`
4. **Update documentation** and dependencies
5. **Add tests** and validation

**Cross-References**:
- → [System Architecture Analysis](claudedocs/system_architecture_analysis.md) for detailed extension guidance

---

## Cross-References

### 📁 File Dependencies
- **Entry Points**: `cli.py` → Platform handlers → Core services
- **Configuration Flow**: `pyproject.toml` → CLI options → Handler initialization
- **Data Flow**: Input → Platform detection → Processing → Output

### 🔗 Key Relationships  
- **CLI Commands** ↔ **Platform Handlers**: Command routing and execution
- **Platform Handlers** ↔ **Core Services**: Processing delegation
- **User Content** ↔ **Platform Handlers**: Batch processing coordination
- **Configuration** ↔ **All Modules**: Settings propagation

### 📚 Documentation Links
- **User Guide**: [README.md](README.md) - Installation, usage, examples
- **System Design**: [claudedocs/system_architecture_analysis.md](claudedocs/system_architecture_analysis.md) - Technical architecture
- **Bilibili Design**: [src/readvideo/user_content/design.md](src/readvideo/user_content/design.md) - User processing design
- **YouTube Design**: [src/readvideo/user_content/youtube_design.md](src/readvideo/user_content/youtube_design.md) - Channel processing design

### 🌐 External References
- **GitHub Repository**: https://github.com/learnerLj/readvideo
- **PyPI Package**: https://pypi.org/project/readvideo/
- **Issue Tracker**: https://github.com/learnerLj/readvideo/issues

---

*This index provides comprehensive navigation for the ReadVideo project. Each section contains cross-references to related components, making it easy to understand relationships and locate specific functionality.*

**Generated by**: Claude Code SuperClaude Framework  
**Last Updated**: 2025-08-26  
**Version**: 0.1.1