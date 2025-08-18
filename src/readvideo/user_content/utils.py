"""Utility functions for user content processing."""

import re
from datetime import datetime
from typing import Optional


def validate_date_format(date_string: str) -> bool:
    """Validate date string format (YYYY-MM-DD).
    
    Args:
        date_string: Date string to validate
        
    Returns:
        True if valid format, False otherwise
    """
    if not date_string:
        return False
    
    try:
        datetime.strptime(date_string, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing invalid characters.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename safe for filesystem
    """
    # Remove or replace invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remove extra spaces and dots
    sanitized = re.sub(r'\s+', '_', sanitized.strip())
    sanitized = re.sub(r'\.+$', '', sanitized)
    
    # Truncate if too long (keep under 200 chars for safety)
    if len(sanitized) > 200:
        sanitized = sanitized[:200]
    
    return sanitized or "untitled"


def format_duration(seconds: int) -> str:
    """Format duration in seconds to human readable format.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted duration string (HH:MM:SS or MM:SS)
    """
    if seconds < 0:
        return "00:00"
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes:02d}:{seconds:02d}"


def extract_video_id_from_url(url: str) -> Optional[str]:
    """Extract BV ID from Bilibili video URL.
    
    Args:
        url: Bilibili video URL
        
    Returns:
        BV ID if found, None otherwise
    """
    patterns = [
        r'/video/(BV[a-zA-Z0-9]+)',
        r'BV([a-zA-Z0-9]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            bv_id = match.group(1) if 'BV' in match.group(0) else f"BV{match.group(1)}"
            return bv_id if bv_id.startswith('BV') else f"BV{bv_id}"
    
    return None