# ReadVideo

[![PyPI version](https://badge.fury.io/py/readvideo.svg)](https://badge.fury.io/py/readvideo)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

A modern Python-based video and audio transcription tool that extracts and transcribes content from YouTube, Bilibili, and local media files. This project is a complete rewrite of the original bash script with improved modularity, performance, and user experience.

## 🚀 Features

### Multi-Platform Support
- **YouTube**: Prioritizes existing subtitles, falls back to audio transcription
- **Bilibili**: Automatically downloads and transcribes audio using BBDown
- **Local Files**: Supports various audio and video file formats

### Intelligent Processing
- **Subtitle Priority**: YouTube videos prioritize `youtube-transcript-api` for existing subtitles
- **Multi-Language Support**: Supports Chinese, English, and more with auto-detection or manual specification
- **Fallback Mechanism**: Automatically falls back to audio transcription when subtitles are unavailable

### High Performance
- **Tool Reuse**: Directly calls installed whisper-cli for native performance
- **Model Reuse**: Utilizes existing models in `~/.whisper-models/` directory
- **Efficient Processing**: Smart temporary file management and cleanup

## 📦 Installation

### Prerequisites
- Python 3.11+
- ffmpeg (system installation)
- whisper-cli (from whisper.cpp)
- yt-dlp (Python package, included)
- BBDown (optional, for Bilibili support)

### Install from PyPI

#### Option 1: Install as a global tool (Recommended)
```bash
# Using uv (recommended - fast and isolated)
uv tool install readvideo

# Using pipx (alternative tool installer)
pipx install readvideo

# Using pip globally
pip install readvideo
```

#### Option 2: Development Installation
```bash
# Clone and install for development
git clone https://github.com/learnerLj/readvideo.git
cd readvideo
uv sync

# Or with pip
pip install -e .
```

### System Dependencies
```bash
# macOS
brew install ffmpeg whisper-cpp

# Ubuntu/Debian
sudo apt install ffmpeg
# Install whisper.cpp from source: https://github.com/ggerganov/whisper.cpp

# Download Whisper model (if not already present)
mkdir -p ~/.whisper-models
# Download ggml-large-v3.bin to ~/.whisper-models/
```

## 🎯 Quick Start

### Basic Usage
```bash
# YouTube video (prioritizes subtitles)
readvideo https://www.youtube.com/watch?v=abc123

# Auto language detection
readvideo --auto-detect https://www.youtube.com/watch?v=abc123

# Bilibili video
readvideo https://www.bilibili.com/video/BV1234567890

# Local audio file
readvideo ~/Music/podcast.mp3

# Local video file
readvideo ~/Videos/lecture.mp4

# Custom output directory
readvideo input.mp4 --output-dir ./transcripts

# Show information only
readvideo input.mp4 --info-only
```

### Command Line Options
```
Options:
  --auto-detect              Enable automatic language detection (default: Chinese)
  --output-dir, -o PATH      Output directory (default: current directory or input file directory)
  --no-cleanup               Do not clean up temporary files
  --info-only                Show input information only, do not process
  --whisper-model PATH       Path to Whisper model file [default: ~/.whisper-models/ggml-large-v3.bin]
  --verbose, -v              Verbose output
  --proxy TEXT               HTTP proxy address (e.g., http://127.0.0.1:8080)
  --help                     Show this message and exit
```

## 🏗️ Architecture

### Project Structure
```
readvideo/
├── pyproject.toml              # Project configuration
├── README.md                   # Project documentation
└── src/readvideo/
    ├── __init__.py             # Package initialization
    ├── cli.py                  # CLI entry point
    ├── core/                   # Core functionality modules
    │   ├── transcript_fetcher.py   # YouTube subtitle fetcher
    │   ├── whisper_wrapper.py      # whisper-cli wrapper
    │   └── audio_processor.py      # Audio processor
    └── platforms/              # Platform handlers
        ├── youtube.py          # YouTube handler
        ├── bilibili.py         # Bilibili handler
        └── local.py            # Local file handler
```

### Core Dependencies
- `youtube-transcript-api`: YouTube subtitle extraction
- `yt-dlp`: YouTube video downloading
- `click`: Command-line interface
- `rich`: Beautiful console output
- `tenacity`: Retry mechanisms
- `ffmpeg`: Audio processing (system dependency)
- `whisper-cli`: Speech transcription (system dependency)

## 🔧 How It Works

### YouTube Processing
1. **Subtitle Priority**: Attempts to fetch existing subtitles using `youtube-transcript-api`
2. **Language Preference**: Prioritizes Chinese (zh, zh-Hans, zh-Hant), then English
3. **Fallback**: If no subtitles available, downloads audio with `yt-dlp`
4. **Transcription**: Converts audio to WAV and transcribes with whisper-cli

### Bilibili Processing
1. **Audio Download**: Uses BBDown to extract audio from Bilibili videos
2. **Format Conversion**: Converts audio to WAV format using ffmpeg
3. **Transcription**: Processes audio with whisper-cli

### Local File Processing
1. **Format Detection**: Automatically detects audio vs video files
2. **Audio Extraction**: Extracts audio tracks from video files using ffmpeg
3. **Format Conversion**: Converts to whisper-compatible WAV format
4. **Transcription**: Processes with whisper-cli

## 📋 Supported Formats

### Audio Formats
- MP3, M4A, WAV, FLAC, OGG, AAC, WMA

### Video Formats  
- MP4, MKV, AVI, MOV, WMV, FLV, WEBM, M4V

## 🛠️ Configuration

### Whisper Model Configuration
```bash
# Default model path
~/.whisper-models/ggml-large-v3.bin

# Custom model
readvideo input.mp4 --whisper-model /path/to/model.bin
```

### Language Options
- `--auto-detect`: Automatic language detection
- Default: Chinese (`zh`)
- YouTube subtitles support multi-language priority

## 🧪 Testing

### Test Examples
```bash
# YouTube video with subtitles
readvideo "https://www.youtube.com/watch?v=JdKVJH3xmlU" --info-only

# Bilibili video
readvideo "https://www.bilibili.com/video/BV1Tjt9zJEdw" --info-only

# Test local file format support
echo "test" > test.txt
readvideo test.txt --info-only  # Should show format error
```

### Debugging
```bash
# Verbose output
readvideo input.mp4 --verbose

# Keep temporary files
readvideo input.mp4 --no-cleanup --verbose

# Information only (no processing)
readvideo input.mp4 --info-only
```

## ⚡ Performance

### Speed Comparison
| Operation | Time | Notes |
|-----------|------|-------|
| YouTube subtitle fetch | ~3-5s | When subtitles available |
| YouTube audio download | ~30s-2min | Depends on video length |
| Audio conversion | ~5-15s | Depends on file size |
| Whisper transcription | ~0.1-0.5x video length | Depends on model and audio length |

### Performance Features
- **Subtitle Priority**: 10-100x faster than audio transcription for YouTube
- **Native Tools**: Direct whisper-cli calls maintain original performance
- **Smart Caching**: Reuses existing models and temporary files efficiently

## 🚨 Troubleshooting

### Common Issues

#### 1. whisper-cli not found
```bash
# Solution: Install whisper.cpp
brew install whisper-cpp  # macOS
# Or compile from source: https://github.com/ggerganov/whisper.cpp
```

#### 2. ffmpeg not found
```bash
# Solution: Install ffmpeg
brew install ffmpeg      # macOS
sudo apt install ffmpeg  # Ubuntu/Debian
```

#### 3. Model file missing
```bash
# Solution: Download whisper model
mkdir -p ~/.whisper-models
# Download ggml-large-v3.bin from whisper.cpp releases
```

#### 4. YouTube IP restrictions
- The tool automatically falls back to audio download when subtitle API is blocked
- Consider using a proxy with `--proxy` option if needed
- Wait some time and retry

#### 5. BBDown not found (Bilibili only)
- Download from [BBDown GitHub](https://github.com/nilaoda/BBDown)
- Ensure it's in your PATH

### Error Handling
- **Graceful Fallbacks**: YouTube subtitle failures automatically retry with audio transcription
- **Intelligent Retries**: Network issues are retried automatically, but IP blocks are not
- **Clear Error Messages**: Descriptive error messages with suggested solutions
- **Cleanup on Failure**: Temporary files are cleaned up even if processing fails

## 🔒 Security Notes

### Cookie Usage
- Browser cookies are used only for video downloads (yt-dlp), not for subtitle API calls
- This follows security recommendations from the youtube-transcript-api maintainer
- Cookies help bypass some YouTube download restrictions

### Privacy
- No data is sent to external services except for downloading content
- All processing happens locally on your machine
- Temporary files are automatically cleaned up

## 🤝 Contributing

This project replaces a bash script with a modern Python implementation. Key design principles:

1. **Maintain Compatibility**: Same functionality as the original bash script
2. **Improve Performance**: Leverage existing tools efficiently
3. **Better UX**: Rich console output and clear error messages
4. **Extensible**: Modular design for easy platform additions

### Adding New Platforms
1. Create a new handler in `platforms/`
2. Implement `validate_url()`, `process()`, and `get_info()` methods
3. Add detection logic in CLI

### Adding New Formats
1. Update format lists in `AudioProcessor`
2. Add corresponding ffmpeg parameters
3. Test with sample files

## 📄 License

This project maintains compatibility with the original bash script while providing a modern Python implementation focused on performance, reliability, and user experience.

## 🙏 Acknowledgments

- [whisper.cpp](https://github.com/ggerganov/whisper.cpp) for high-performance speech recognition
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) for robust video downloading
- [youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api) for subtitle extraction
- [BBDown](https://github.com/nilaoda/BBDown) for Bilibili support