"""Simple utilities for ReadVideo application."""

import re
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, List, Optional, Union


# File utilities
def sanitize_filename(filename: str, max_length: int = 100) -> str:
    """Sanitize filename to be safe for filesystem."""
    if not filename:
        return "untitled"
    
    # Replace problematic characters
    safe_name = re.sub(r'[<>:"/\\|?*]', '_', filename)
    safe_name = re.sub(r'[\x00-\x1f\x7f]', '', safe_name)
    safe_name = safe_name.strip(' .')
    
    if len(safe_name) > max_length:
        safe_name = safe_name[:max_length].rstrip(' .')
    
    return safe_name or "untitled"


def detect_file_format(file_path: Union[str, Path]) -> str:
    """Get file extension without dot."""
    return Path(file_path).suffix.lower().lstrip('.') or "unknown"


def cleanup_files(file_paths: List[Union[str, Path]]) -> None:
    """Delete multiple files safely."""
    for file_path in file_paths or []:
        try:
            Path(file_path).unlink(missing_ok=True)
        except (OSError, PermissionError):
            pass


def validate_file_path(file_path: Union[str, Path]) -> Path:
    """Validate and normalize file path."""
    return Path(file_path).resolve()


def get_file_info(file_path: Union[str, Path]):
    """Get basic file information."""
    path = Path(file_path)
    if not path.exists():
        return {"exists": False, "path": str(path)}
    
    stat = path.stat()
    return {
        "exists": True,
        "path": str(path),
        "size": stat.st_size,
        "is_file": path.is_file(),
        "format": detect_file_format(path)
    }


def processing_context(temp_files: List[Union[str, Path]]):
    """Simple context for cleanup."""
    class ProcessingContext:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            cleanup_files(temp_files)
    return ProcessingContext()


def cleanup_file_list(file_paths: List[Union[str, Path]], ignore_errors: bool = True) -> List[str]:
    """Cleanup files and return failed paths."""
    failed = []
    for file_path in file_paths or []:
        try:
            Path(file_path).unlink(missing_ok=True)
        except (OSError, PermissionError):
            if not ignore_errors:
                failed.append(str(file_path))
    return failed


# Video utilities
def extract_youtube_video_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from URL."""
    if not url:
        return None
    patterns = [
        r"(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})",
        r"youtube\.com\/.*[?&]v=([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def extract_bilibili_video_id(url: str) -> Optional[str]:
    """Extract Bilibili video ID from URL."""
    if not url:
        return None
    match = re.search(r"bilibili\.com\/video\/(BV[a-zA-Z0-9]+)", url)
    return match.group(1) if match else None


def is_youtube_url(url: str) -> bool:
    """Check if URL is YouTube."""
    return bool(url and any(domain in url.lower() 
                           for domain in ["youtube.com", "youtu.be"]))


def is_bilibili_url(url: str) -> bool:
    """Check if URL is Bilibili."""
    return bool(url and "bilibili.com" in url.lower())


def detect_video_platform(url: str) -> Optional[str]:
    """Detect platform from URL."""
    if is_youtube_url(url):
        return "youtube"
    elif is_bilibili_url(url):
        return "bilibili"
    return None


# Resource management
@contextmanager
def managed_temp_directory(prefix: str = "readvideo_") -> Generator[str, None, None]:
    """Create temporary directory with auto cleanup."""
    temp_dir = tempfile.mkdtemp(prefix=prefix)
    try:
        yield temp_dir
    finally:
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass


__all__ = [
    'sanitize_filename', 'detect_file_format', 'cleanup_files',
    'validate_file_path', 'get_file_info', 'processing_context', 'cleanup_file_list',
    'extract_youtube_video_id', 'extract_bilibili_video_id',
    'is_youtube_url', 'is_bilibili_url', 'detect_video_platform',
    'managed_temp_directory'
]