"""Utility functions for user content processing."""

from datetime import datetime
import re
from typing import Optional, Tuple


def validate_date_format(date_string: str) -> bool:
    """Validate date string format (YYYY-MM-DD).

    Args:
        date_string: Date string to validate

    Returns:
        True if valid format, False otherwise
    """
    if not date_string:
        return False

    # Check exact format first (must be exactly YYYY-MM-DD)
    import re

    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_string):
        return False

    try:
        datetime.strptime(date_string, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def validate_date_with_range_check(date_string: str) -> Tuple[bool, str]:
    """Validate date string with comprehensive checks.

    Args:
        date_string: Date string to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not date_string:
        return False, "Date string is empty"

    # Check exact format first (must be exactly YYYY-MM-DD)
    import re

    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_string):
        return False, "Invalid date format. Use YYYY-MM-DD format (e.g., 2024-01-15)"

    # Check basic format
    try:
        parsed_date = datetime.strptime(date_string, "%Y-%m-%d")
    except ValueError:
        return False, "Invalid date format. Use YYYY-MM-DD format (e.g., 2024-01-15)"

    # Check if date is in reasonable range
    current_date = datetime.now()

    # Don't allow dates too far in the past (before 2005 when Bilibili wasn't around)
    min_date = datetime(2005, 1, 1)
    if parsed_date < min_date:
        return (
            False,
            f"Date too early. Bilibili videos start from "
            f"{min_date.strftime('%Y-%m-%d')}",
        )

    # Don't allow future dates (with 1 day buffer for timezone differences)
    max_date = current_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    if parsed_date.date() > max_date.date():
        return (
            False,
            f"Future dates not allowed. Latest date: {max_date.strftime('%Y-%m-%d')}",
        )

    return True, ""


def parse_date_to_timestamp_range(date_string: str) -> Tuple[int, int]:
    """Parse date string to UTC timestamp range covering the whole day.

    Args:
        date_string: Date string in YYYY-MM-DD format

    Returns:
        Tuple of (start_timestamp, end_timestamp) covering the entire day in UTC

    Raises:
        ValueError: If date format is invalid
    """
    try:
        # Parse date (assumes local timezone)
        parsed_date = datetime.strptime(date_string, "%Y-%m-%d")

        # Create start of day (00:00:00) and end of day (23:59:59) in local timezone
        start_of_day = parsed_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = parsed_date.replace(
            hour=23, minute=59, second=59, microsecond=999999
        )

        # Convert to UTC timestamps
        start_timestamp = int(start_of_day.timestamp())
        end_timestamp = int(end_of_day.timestamp())

        return start_timestamp, end_timestamp

    except ValueError as e:
        raise ValueError(
            f"Invalid date format: {date_string}. Use YYYY-MM-DD format"
        ) from e


def sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing invalid characters.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename safe for filesystem
    """
    # Remove or replace invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', "_", filename)
    # Remove extra spaces and dots
    sanitized = re.sub(r"\s+", "_", sanitized.strip())
    sanitized = re.sub(r"\.+$", "", sanitized)

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
    patterns = [r"/video/(BV[a-zA-Z0-9]+)", r"BV([a-zA-Z0-9]+)"]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            bv_id = match.group(1) if "BV" in match.group(0) else f"BV{match.group(1)}"
            return bv_id if bv_id.startswith("BV") else f"BV{bv_id}"

    return None
