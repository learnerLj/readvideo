"""YouTube platform handler with transcript priority."""

import os
from pathlib import Path
import subprocess
from typing import Any, Dict, Optional

from rich.console import Console
from tenacity import RetryError

from ..core.audio_processor import AudioProcessingError, AudioProcessor
from ..core.transcript_fetcher import (
    TranscriptFetchError,
    YouTubeTranscriptFetcher,
    is_youtube_url,
)
from ..core.whisper_wrapper import WhisperWrapper

console = Console()


class YouTubeHandler:
    """Handler for processing YouTube videos with transcript priority."""

    def __init__(
        self,
        whisper_model_path: str = "~/.whisper-models/ggml-large-v3.bin",
        prefer_cookies: bool = True,
        proxy: Optional[str] = None,
    ):
        """Initialize YouTube handler.

        Args:
            whisper_model_path: Path to whisper model for fallback transcription
            prefer_cookies: Whether to use browser cookies for yt-dlp video download
            proxy: Proxy URL for transcript API
        """
        # Setup proxy configuration
        proxies = None
        if proxy:
            proxies = {"http": proxy, "https": proxy}

        # Note: No cookies for transcript API to avoid account ban risk
        self.transcript_fetcher = YouTubeTranscriptFetcher(proxies=proxies)
        self.audio_processor = AudioProcessor()
        self.whisper_wrapper = WhisperWrapper(whisper_model_path)
        self.prefer_cookies = prefer_cookies  # Only for yt-dlp downloads

    def validate_url(self, url: str) -> bool:
        """Validate that URL is a YouTube URL.

        Args:
            url: URL to validate

        Returns:
            True if valid YouTube URL
        """
        return is_youtube_url(url)

    def process(
        self,
        url: str,
        auto_detect: bool = False,
        output_dir: Optional[str] = None,
        cleanup: bool = True,
    ) -> Dict[str, Any]:
        """Process YouTube video with transcript priority.

        Args:
            url: YouTube video URL
            auto_detect: Whether to use auto language detection for whisper
            output_dir: Output directory for files
            cleanup: Whether to clean up temporary files

        Returns:
            Dict containing processing results
        """
        if not self.validate_url(url):
            raise ValueError(f"Invalid YouTube URL: {url}")

        console.print(f"🎬 Processing YouTube video: {url}", style="cyan")

        # Set up output directory
        if output_dir is None:
            output_dir = os.getcwd()
        else:
            os.makedirs(output_dir, exist_ok=True)

        # Try to get transcript first (fastest method)
        try:
            return self._process_with_transcript(url, output_dir)
        except (TranscriptFetchError, RetryError) as e:
            console.print(
                f"📝 No existing subtitles, using audio transcription: {e}",
                style="yellow",
            )
            return self._process_with_audio_transcription(
                url, auto_detect, output_dir, cleanup
            )

    def _process_with_transcript(self, url: str, output_dir: str) -> Dict[str, Any]:
        """Process video using available transcripts.

        Args:
            url: YouTube video URL
            output_dir: Output directory

        Returns:
            Dict containing transcript results
        """
        # Define language preference
        languages = ["zh", "zh-Hans", "zh-Hant", "en"]

        # Fetch transcript
        transcript_data = self.transcript_fetcher.fetch_transcript_from_url(
            url, languages=languages, prefer_manual=True
        )

        # Generate output filename
        video_id = self.transcript_fetcher.extract_video_id(url)
        output_file = os.path.join(output_dir, f"{video_id}.txt")

        # Save transcript
        self.transcript_fetcher.save_transcript(transcript_data, output_file)

        return {
            "success": True,
            "method": "transcript",
            "platform": "youtube",
            "url": url,
            "video_id": video_id,
            "output_file": output_file,
            "text": transcript_data["text"],
            "transcript_info": transcript_data["transcript_info"],
            "segment_count": transcript_data["segment_count"],
        }

    def _process_with_audio_transcription(
        self, url: str, auto_detect: bool, output_dir: str, cleanup: bool
    ) -> Dict[str, Any]:
        """Process video by downloading audio and transcribing.

        Args:
            url: YouTube video URL
            auto_detect: Whether to use auto language detection
            output_dir: Output directory
            cleanup: Whether to clean up temporary files

        Returns:
            Dict containing transcription results
        """
        temp_files = []

        try:
            # Download audio using yt-dlp
            console.print("🎬 Downloading audio from YouTube...", style="cyan")
            console.print(
                "💡 Tip: Audio extraction may take a few minutes, please be patient",
                style="dim",
            )
            audio_file = self._download_audio(url, output_dir)
            console.print("✅ Audio download completed", style="green")
            temp_files.append(audio_file)

            # Convert to WAV for whisper
            wav_file = self._convert_to_wav(audio_file, output_dir)
            temp_files.append(wav_file)

            # Transcribe with whisper-cli
            language = None if auto_detect else "zh"
            result = self.whisper_wrapper.transcribe(
                wav_file,
                language=language,
                auto_detect=auto_detect,
                output_dir=output_dir,
            )

            # Extract video ID for naming
            video_id = self.transcript_fetcher.extract_video_id(url)
            final_output = os.path.join(output_dir, f"{video_id}.txt")

            # Copy transcription to final location
            if (
                os.path.exists(result["output_file"])
                and result["output_file"] != final_output
            ):
                os.rename(result["output_file"], final_output)
                result["output_file"] = final_output

            return {
                "success": True,
                "method": "transcription",
                "platform": "youtube",
                "url": url,
                "video_id": video_id,
                "output_file": final_output,
                "text": result["text"],
                "language": result["language"],
                "audio_file": audio_file,
                "temp_files": temp_files if not cleanup else [],
            }

        except Exception:
            if cleanup:
                self.audio_processor.cleanup_temp_files(temp_files)
            raise
        finally:
            if cleanup:
                self.audio_processor.cleanup_temp_files(temp_files)

    def _download_audio(self, url: str, output_dir: str) -> str:
        """Download audio from YouTube using yt-dlp.

        Args:
            url: YouTube video URL
            output_dir: Output directory

        Returns:
            Path to downloaded audio file
        """
        try:
            # Build yt-dlp command
            cmd = [
                "yt-dlp",
                "-x",  # Extract audio
                "--audio-format",
                "m4a",
                "--force-overwrites",  # Overwrite existing files
                "--progress",  # Show progress even with other options
            ]

            # Add cookies if available and preferred
            if self.prefer_cookies:
                cmd.extend(["--cookies-from-browser", "chrome"])

            # Set output directory
            original_dir = os.getcwd()
            os.chdir(output_dir)

            try:
                cmd.append(url)
                subprocess.run(cmd, check=True)

                # Find downloaded file (yt-dlp creates files with ] in name)
                m4a_files = [f for f in os.listdir(".") if f.endswith("].m4a")]
                if not m4a_files:
                    raise AudioProcessingError("No audio file found after download")

                # Get the most recent file
                audio_file = max(m4a_files, key=os.path.getctime)
                return os.path.join(output_dir, audio_file)

            finally:
                os.chdir(original_dir)

        except subprocess.CalledProcessError as e:
            raise AudioProcessingError(f"yt-dlp failed: {e}")
        except FileNotFoundError:
            raise AudioProcessingError("yt-dlp not found. Please install yt-dlp.")

    def _convert_to_wav(self, audio_file: str, output_dir: str) -> str:
        """Convert audio file to WAV format for whisper.

        Args:
            audio_file: Path to input audio file
            output_dir: Output directory

        Returns:
            Path to converted WAV file
        """
        basename = Path(audio_file).stem
        wav_file = os.path.join(output_dir, f"{basename}.wav")

        return self.audio_processor.convert_audio_format(
            audio_file, wav_file, target_format="wav", sample_rate=16000, channels=1
        )

    def get_video_info(self, url: str) -> Dict[str, Any]:
        """Get video information without downloading.

        Args:
            url: YouTube video URL

        Returns:
            Dict containing video information
        """
        if not self.validate_url(url):
            raise ValueError(f"Invalid YouTube URL: {url}")

        video_id = self.transcript_fetcher.extract_video_id(url)
        if not video_id:
            raise ValueError(f"Could not extract video ID from URL: {url}")

        try:
            # Get available transcripts
            available_transcripts = self.transcript_fetcher.get_available_transcripts(
                video_id
            )

            return {
                "video_id": video_id,
                "url": url,
                "platform": "youtube",
                "has_transcripts": bool(
                    available_transcripts["manual"]
                    or available_transcripts["generated"]
                ),
                "available_transcripts": available_transcripts,
            }

        except (TranscriptFetchError, RetryError):
            return {
                "video_id": video_id,
                "url": url,
                "platform": "youtube",
                "has_transcripts": False,
                "available_transcripts": {
                    "manual": [],
                    "generated": [],
                    "translatable": [],
                },
            }
