"""YouTube transcript fetcher using youtube-transcript-api."""

import re
from typing import Any, Dict, List, Optional

import requests
from rich.console import Console
from tenacity import (retry, retry_if_exception_type, stop_after_attempt,
                      wait_fixed)
from youtube_transcript_api import (NoTranscriptFound, TranscriptsDisabled,
                                    YouTubeTranscriptApi)
from youtube_transcript_api.formatters import TextFormatter

console = Console()


class TranscriptFetchError(Exception):
    """Exception raised when transcript fetching fails."""

    pass


class RetryableTranscriptError(Exception):
    """Exception for retryable transcript errors (rate limits, network issues)."""

    pass


class YouTubeTranscriptFetcher:
    """Fetcher for YouTube video transcripts using youtube-transcript-api."""

    def __init__(
        self,
        cookies_path: Optional[str] = None,
        proxies: Optional[Dict] = None,
    ):
        """Initialize the transcript fetcher.

        Args:
            cookies_path: Path to cookies file (Netscape format)
            proxies: Proxy configuration dict
        """
        # Create custom session if needed
        http_client = None
        if cookies_path or proxies:
            http_client = requests.Session()

            if proxies:
                http_client.proxies.update(proxies)

            if cookies_path:
                self._load_cookies_from_file(http_client, cookies_path)

        self.api = YouTubeTranscriptApi(http_client=http_client)
        self.formatter = TextFormatter()
        self.cookies_path = cookies_path

    def _load_cookies_from_file(
        self, session: requests.Session, cookies_path: str
    ) -> None:
        """Load cookies from file into session.

        Args:
            session: Requests session to add cookies to
            cookies_path: Path to cookies file
        """
        try:
            import http.cookiejar

            cookie_jar = http.cookiejar.MozillaCookieJar(cookies_path)
            cookie_jar.load(ignore_discard=True, ignore_expires=True)
            session.cookies.update(cookie_jar)  # type: ignore
            console.print(
                f"🍪 Loaded cookies from file: {cookies_path}", style="dim"
            )
        except Exception as e:
            console.print(
                f"⚠️ Unable to load cookies file: {e}", style="yellow"
            )

    def extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from YouTube URL.

        Args:
            url: YouTube URL

        Returns:
            Video ID or None if not found
        """
        patterns = [
            r"(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)"
            r"([a-zA-Z0-9_-]{11})",
            r"youtube\.com\/.*[?&]v=([a-zA-Z0-9_-]{11})",
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(1),
        retry=retry_if_exception_type(RetryableTranscriptError),
        before_sleep=lambda retry_state: console.print(
            f"🔄 Attempt {retry_state.attempt_number + 1} to get subtitle info... "
            "(access restricted)",
            style="yellow",
        ),
    )
    def get_available_transcripts(self, video_id: str) -> Dict[str, Any]:
        """Get list of available transcripts for a video.

        Args:
            video_id: YouTube video ID

        Returns:
            Dict containing available transcripts info
        """
        try:
            transcript_list = self.api.list(video_id)

            available: Dict[str, List[Dict[str, Any]]] = {
                "manual": [],
                "generated": [],
                "translatable": [],
            }

            for transcript in transcript_list:
                info = {
                    "language": transcript.language,
                    "language_code": transcript.language_code,
                    "is_generated": transcript.is_generated,
                    "is_translatable": transcript.is_translatable,
                }

                if transcript.is_generated:
                    available["generated"].append(info)
                else:
                    available["manual"].append(info)

                if transcript.is_translatable:
                    available["translatable"].append(info)

            return available

        except (TranscriptsDisabled, NoTranscriptFound) as e:
            raise TranscriptFetchError(
                f"No transcripts available for video {video_id}: {e}"
            )
        except Exception as e:
            error_msg = str(e)
            # Check if it's specifically an IP block - don't retry these
            if any(
                keyword in error_msg.lower()
                for keyword in [
                    "blocking requests from your ip",
                    "ip has been blocked",
                    "cloud provider",
                ]
            ):
                raise TranscriptFetchError(f"IP blocked by YouTube: {e}")
            # Check if it's a retryable error (temporary network issues, etc.)
            elif any(
                keyword in error_msg.lower()
                for keyword in ["timeout", "connection", "network"]
            ):
                raise RetryableTranscriptError(
                    f"Retryable error fetching transcript list: {e}"
                )
            raise TranscriptFetchError(f"Error fetching transcript list: {e}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(1),
        retry=retry_if_exception_type(RetryableTranscriptError),
        before_sleep=lambda retry_state: console.print(
            f"🔄 Attempt {retry_state.attempt_number + 1} to get subtitles... "
            "(access restricted)",
            style="yellow",
        ),
    )
    def fetch_transcript(
        self,
        video_id: str,
        languages: Optional[List[str]] = None,
        prefer_manual: bool = True,
    ) -> Dict[str, Any]:
        """Fetch transcript for a YouTube video.

        Args:
            video_id: YouTube video ID
            languages: Preferred languages in order of priority (e.g., ['zh', 'en'])
            prefer_manual: Whether to prefer manually created transcripts

        Returns:
            Dict containing transcript data and metadata
        """
        if languages is None:
            languages = ["zh", "zh-Hans", "zh-Hant", "en"]

        try:
            transcript_list = self.api.list(video_id)

            # Try to find transcript in preferred order
            transcript = None
            selected_info = None

            if prefer_manual:
                # First try manual transcripts
                try:
                    transcript = (
                        transcript_list.find_manually_created_transcript(
                            languages
                        )
                    )
                    selected_info = {
                        "type": "manual",
                        "language": transcript.language,
                        "language_code": transcript.language_code,
                    }
                    console.print(
                        f"✅ Found manual subtitles: {transcript.language}",
                        style="green",
                    )
                except NoTranscriptFound:
                    pass

            # If no manual transcript found, try generated ones
            if transcript is None:
                try:
                    transcript = transcript_list.find_generated_transcript(
                        languages
                    )
                    selected_info = {
                        "type": "generated",
                        "language": transcript.language,
                        "language_code": transcript.language_code,
                    }
                    console.print(
                        f"✅ Found auto-generated subtitles: {transcript.language}",
                        style="yellow",
                    )
                except NoTranscriptFound:
                    pass

            # Last resort: try any available transcript
            if transcript is None:
                try:
                    transcript = transcript_list.find_transcript(languages)
                    selected_info = {
                        "type": "auto",
                        "language": transcript.language,
                        "language_code": transcript.language_code,
                    }
                    console.print(
                        f"✅ Found subtitles: {transcript.language}",
                        style="cyan",
                    )
                except NoTranscriptFound:
                    raise TranscriptFetchError(
                        f"No transcript found in languages: {languages}"
                    )

            # Fetch the actual transcript data
            transcript_data = transcript.fetch()

            # Format as plain text
            formatted_text = self.formatter.format_transcript(transcript_data)

            return {
                "success": True,
                "text": formatted_text,
                "video_id": video_id,
                "transcript_info": selected_info,
                "raw_data": transcript_data,
                "segment_count": len(transcript_data),
            }

        except TranscriptsDisabled:
            raise TranscriptFetchError(
                f"Transcripts are disabled for video {video_id}"
            )
        except NoTranscriptFound:
            raise TranscriptFetchError(
                f"No transcript found for video {video_id} in languages: {languages}"
            )
        except Exception as e:
            error_msg = str(e)
            # Check if it's specifically an IP block - don't retry these
            if any(
                keyword in error_msg.lower()
                for keyword in [
                    "blocking requests from your ip",
                    "ip has been blocked",
                    "cloud provider",
                ]
            ):
                raise TranscriptFetchError(f"IP blocked by YouTube: {e}")
            # Check if it's a retryable error (temporary network issues, etc.)
            elif any(
                keyword in error_msg.lower()
                for keyword in ["timeout", "connection", "network"]
            ):
                raise RetryableTranscriptError(
                    f"Retryable error fetching transcript: {e}"
                )
            raise TranscriptFetchError(f"Error fetching transcript: {e}")

    def fetch_transcript_from_url(
        self,
        url: str,
        languages: Optional[List[str]] = None,
        prefer_manual: bool = True,
    ) -> Dict[str, Any]:
        """Fetch transcript from YouTube URL.

        Args:
            url: YouTube URL
            languages: Preferred languages in order of priority
            prefer_manual: Whether to prefer manually created transcripts

        Returns:
            Dict containing transcript data and metadata
        """
        video_id = self.extract_video_id(url)
        if not video_id:
            raise TranscriptFetchError(
                f"Could not extract video ID from URL: {url}"
            )

        console.print(f"🔍 Checking video subtitles: {video_id}", style="cyan")

        return self.fetch_transcript(video_id, languages, prefer_manual)

    def save_transcript(
        self, transcript_data: Dict[str, Any], output_file: str
    ) -> None:
        """Save transcript to file.

        Args:
            transcript_data: Transcript data from fetch_transcript
            output_file: Path to output file
        """
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(transcript_data["text"])

            console.print(f"✅ Subtitles saved: {output_file}", style="green")

        except Exception as e:
            raise TranscriptFetchError(f"Error saving transcript: {e}")


def is_youtube_url(url: str) -> bool:
    """Check if URL is a YouTube URL.

    Args:
        url: URL to check

    Returns:
        True if it's a YouTube URL
    """
    youtube_patterns = [r"youtube\.com", r"youtu\.be", r"m\.youtube\.com"]

    return any(
        re.search(pattern, url, re.IGNORECASE) for pattern in youtube_patterns
    )
