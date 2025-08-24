"""Bilibili platform handler."""

import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console

from ..core.audio_processor import AudioProcessingError, AudioProcessor
from ..core.whisper_wrapper import WhisperWrapper

console = Console()
logger = logging.getLogger(__name__)


class BilibiliHandler:
    """Handler for processing Bilibili videos."""

    def __init__(self, whisper_model_path: str = "~/.whisper-models/ggml-large-v3.bin"):
        """Initialize Bilibili handler.

        Args:
            whisper_model_path: Path to whisper model for transcription
        """
        self.audio_processor = AudioProcessor()
        self.whisper_wrapper = WhisperWrapper(whisper_model_path)
        self.verify_bbdown()
        self._ytdlp_available = self._check_ytdlp_availability()

    def verify_bbdown(self) -> None:
        """Verify that BBDown is available."""
        import shutil

        if not shutil.which("BBDown"):
            console.print(
                "⚠️ Warning: BBDown not found. Bilibili processing may not work.",
                style="yellow",
            )

    def _check_ytdlp_availability(self) -> bool:
        """Check if yt-dlp is available as backup downloader.

        Returns:
            True if yt-dlp is available, False otherwise
        """
        import shutil

        try:
            if shutil.which("yt-dlp"):
                # Verify yt-dlp actually works
                result = subprocess.run(
                    ["yt-dlp", "--version"], capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    logger.debug(f"yt-dlp available: {result.stdout.strip()}")
                    return True
            return False
        except Exception as e:
            logger.debug(f"yt-dlp availability check failed: {e}")
            return False

    def _is_ytdlp_available(self) -> bool:
        """Check if yt-dlp is available for use.

        Returns:
            True if yt-dlp can be used as backup
        """
        return getattr(self, "_ytdlp_available", False)

    def validate_url(self, url: str) -> bool:
        """Validate that URL is a Bilibili URL.

        Args:
            url: URL to validate

        Returns:
            True if valid Bilibili URL
        """
        bilibili_patterns = [r"bilibili\.com", r"b23\.tv", r"m\.bilibili\.com"]

        return any(
            re.search(pattern, url, re.IGNORECASE) for pattern in bilibili_patterns
        )

    def extract_bv_id(self, url: str) -> Optional[str]:
        """Extract BV ID from Bilibili URL.

        Args:
            url: Bilibili URL

        Returns:
            BV ID or None if not found
        """
        patterns = [r"/video/(BV[a-zA-Z0-9]+)", r"BV([a-zA-Z0-9]+)"]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                bv_id = (
                    match.group(1) if "BV" in match.group(0) else f"BV{match.group(1)}"
                )
                return bv_id if bv_id.startswith("BV") else f"BV{bv_id}"

        return None

    def sanitize_filename(self, filename: str, max_length: int = 50) -> str:
        """Sanitize filename by removing invalid characters.

        Args:
            filename: Original filename
            max_length: Maximum length for the filename part

        Returns:
            Sanitized filename safe for all operating systems
        """
        # Remove or replace invalid characters
        # Windows reserved: < > : " | ? * \ /
        # Also remove other problematic characters
        invalid_chars = r'[<>:"|?*\\/]'
        sanitized = re.sub(invalid_chars, "_", filename)

        # Remove multiple consecutive underscores/spaces
        sanitized = re.sub(r"[_\s]+", "_", sanitized)

        # Remove leading/trailing underscores
        sanitized = sanitized.strip("_")

        # Truncate if too long, but try to keep word boundaries
        if len(sanitized) > max_length:
            truncated = sanitized[:max_length]
            # Try to end at a word boundary
            last_underscore = truncated.rfind("_")
            if last_underscore > max_length * 0.7:  # If underscore is in the last 30%
                truncated = truncated[:last_underscore]
            sanitized = truncated.rstrip("_")

        # Ensure not empty
        return sanitized if sanitized else "video"

    def generate_filename(
        self, bv_id: str, video_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate filename based on video info and BV ID.

        Args:
            bv_id: Bilibili BV ID
            video_info: Optional video metadata with title and date

        Returns:
            Generated filename without extension
        """
        if not video_info:
            return bv_id

        # Extract date and title
        date = video_info.get("created_date", "")
        title = video_info.get("title", "")

        if not date or not title:
            return bv_id

        # Sanitize title
        safe_title = self.sanitize_filename(title)

        # Build filename: date_title_bvid
        filename = f"{date}_{safe_title}_{bv_id}"

        # Ensure total length is reasonable (200 chars should be safe for most systems)
        if len(filename) > 200:
            # Recalculate with shorter title
            max_title_length = 200 - len(date) - len(bv_id) - 2  # 2 for underscores
            safe_title = self.sanitize_filename(title, max_title_length)
            filename = f"{date}_{safe_title}_{bv_id}"

        return filename

    def process(
        self,
        url: str,
        auto_detect: bool = False,
        output_dir: Optional[str] = None,
        cleanup: bool = True,
        silent: bool = False,
        video_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Process Bilibili video by downloading and transcribing audio.

        Args:
            url: Bilibili video URL
            auto_detect: Whether to use auto language detection for whisper
            output_dir: Output directory for files
            cleanup: Whether to clean up temporary files
            silent: Whether to suppress detailed output (for batch processing)
            video_info: Optional video metadata for improved file naming

        Returns:
            Dict containing processing results
        """
        if not self.validate_url(url):
            raise ValueError(f"Invalid Bilibili URL: {url}")

        console.print(f"🎬 Processing Bilibili video: {url}", style="cyan")

        # Set up output directory
        if output_dir is None:
            output_dir = os.getcwd()
        else:
            os.makedirs(output_dir, exist_ok=True)

        temp_files = []

        try:
            # Download audio using BBDown
            console.print("🎬 Downloading audio from Bilibili...", style="cyan")
            audio_file = self._download_audio(url, output_dir)
            temp_files.append(audio_file)

            # Convert to WAV for whisper
            console.print("🔄 Converting audio format...", style="cyan")
            wav_file = self._convert_to_wav(audio_file, output_dir)
            temp_files.append(wav_file)

            # Transcribe with whisper-cli
            language = None if auto_detect else "zh"
            result = self.whisper_wrapper.transcribe(
                wav_file,
                language=language,
                auto_detect=auto_detect,
                output_dir=output_dir,
                silent=silent,
            )

            # Generate filename based on video info
            bv_id = self.extract_bv_id(url) or "bilibili_video"
            filename = self.generate_filename(bv_id, video_info)
            final_output = os.path.join(output_dir, f"{filename}.txt")

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
                "platform": "bilibili",
                "url": url,
                "bv_id": bv_id,
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

    def _download_with_ytdlp(self, url: str, output_dir: str) -> str:
        """Download audio using yt-dlp as backup method.

        Args:
            url: Bilibili video URL
            output_dir: Output directory

        Returns:
            Path to downloaded audio file
        """
        try:
            # Build yt-dlp command for audio extraction
            cmd = [
                "yt-dlp",
                "--extract-audio",
                "--audio-format",
                "m4a",
                "--no-playlist",
                url,
            ]

            # Set output directory
            original_dir = os.getcwd()
            os.chdir(output_dir)

            try:
                logger.info("🔄 Attempting download with yt-dlp...")
                result = subprocess.run(
                    cmd, capture_output=True, text=True, check=True, timeout=300
                )
                logger.debug(f"yt-dlp stdout: {result.stdout[:500]}...")

                # Find the downloaded audio file
                # yt-dlp creates files like "视频标题 [BV1234567].m4a"
                m4a_files = [f for f in os.listdir(".") if f.endswith(".m4a")]

                if not m4a_files:
                    raise AudioProcessingError(
                        "No audio file found after yt-dlp download"
                    )

                # Get the most recent file (in case there are multiple)
                audio_file = max(m4a_files, key=os.path.getmtime)

                # Basic validation
                file_size = os.path.getsize(audio_file)
                if file_size < 10000:  # < 10KB probably not valid
                    raise AudioProcessingError(
                        f"Downloaded file too small: {file_size} bytes"
                    )

                logger.info(f"✅ Downloaded with yt-dlp: {audio_file}")
                return os.path.join(output_dir, audio_file)

            finally:
                os.chdir(original_dir)

        except subprocess.TimeoutExpired:
            raise AudioProcessingError("yt-dlp download timed out after 5 minutes")
        except subprocess.CalledProcessError as e:
            error_msg = f"yt-dlp failed with exit code {e.returncode}"
            if e.stderr:
                error_msg += f": {e.stderr[:300]}"
            raise AudioProcessingError(error_msg)
        except FileNotFoundError:
            raise AudioProcessingError(
                "yt-dlp not found. Please install: pip install yt-dlp"
            )
        except Exception as e:
            raise AudioProcessingError(f"yt-dlp download failed: {str(e)}")

    def _download_with_bbdown(self, url: str, output_dir: str) -> str:
        """Download audio from Bilibili using BBDown.

        Args:
            url: Bilibili video URL
            output_dir: Output directory

        Returns:
            Path to downloaded audio file
        """
        try:
            # Build BBDown command
            cmd = ["BBDown", "--audio-only", url]

            # Set output directory
            original_dir = os.getcwd()
            os.chdir(output_dir)

            try:
                # Run BBDown and capture output for debugging
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                logger.debug(f"BBDown stdout: {result.stdout[:500]}...")

                # Find audio files in current directory and subdirectories
                audio_files = self._find_audio_files(".")
                logger.debug(
                    f"Found {len(audio_files)} potential audio files: {audio_files}"
                )

                if not audio_files:
                    # List all files for debugging
                    all_files = []
                    for root, dirs, files in os.walk("."):
                        for file in files:
                            all_files.append(os.path.join(root, file))
                    logger.error(f"All files found: {all_files}")

                    raise AudioProcessingError(
                        f"No audio file found after BBDown download. "
                        f"Found {len(all_files)} files: {all_files[:5]}"
                    )

                # Validate and get the best audio file
                valid_audio_file = self._get_valid_audio_file(audio_files)
                return os.path.join(output_dir, valid_audio_file)

            finally:
                os.chdir(original_dir)

        except subprocess.CalledProcessError as e:
            error_msg = f"BBDown failed with exit code {e.returncode}"
            if e.stdout:
                error_msg += f"\nStdout: {e.stdout[:300]}..."
            if e.stderr:
                error_msg += f"\nStderr: {e.stderr[:300]}..."
            raise AudioProcessingError(error_msg)
        except FileNotFoundError:
            raise AudioProcessingError(
                "BBDown not found. Please install BBDown to download from Bilibili."
            )

    def _download_audio(self, url: str, output_dir: str) -> str:
        """Download audio from Bilibili with fallback support."""
        # Try BBDown first
        try:
            return self._download_with_bbdown(url, output_dir)
        except AudioProcessingError as e:
            # Clean up BBDown residual files/directories
            self._cleanup_bbdown_residuals(output_dir)

            # Try yt-dlp as backup
            if self._is_ytdlp_available():
                logger.warning(f"BBDown failed, trying yt-dlp: {e}")
                return self._download_with_ytdlp(url, output_dir)
            else:
                raise AudioProcessingError(f"{e} | Try: pip install yt-dlp")

    def _cleanup_bbdown_residuals(self, output_dir: str) -> None:
        """Clean up BBDown residual files and directories after failure."""
        import shutil

        try:
            # BBDown creates numbered subdirectories (e.g., 115032964796336/)
            for item in os.listdir(output_dir):
                item_path = os.path.join(output_dir, item)
                # Check if it's a directory with only digits in the name
                if os.path.isdir(item_path) and item.isdigit():
                    logger.debug(f"Cleaning up BBDown residual directory: {item_path}")
                    shutil.rmtree(item_path)
        except Exception as e:
            # Don't fail the whole process if cleanup fails
            logger.debug(f"Failed to cleanup BBDown residuals: {e}")

    def _find_audio_files(self, search_dir: str) -> List[str]:
        """Find all potential audio files in directory and subdirectories.

        Args:
            search_dir: Directory to search in

        Returns:
            List of relative paths to potential audio files
        """
        audio_extensions = [".m4a", ".mp3", ".aac", ".wav", ".flac", ".ogg"]
        audio_files = []

        for root, dirs, files in os.walk(search_dir):
            for file in files:
                if any(file.lower().endswith(ext) for ext in audio_extensions):
                    # Get relative path from search_dir
                    relative_path = os.path.relpath(
                        os.path.join(root, file), search_dir
                    )
                    audio_files.append(relative_path)

        return audio_files

    def _get_valid_audio_file(self, audio_files: List[str]) -> str:
        """Get the first valid audio file from the list.

        Args:
            audio_files: List of potential audio file paths

        Returns:
            Path to valid audio file

        Raises:
            AudioProcessingError: If no valid audio files found
        """
        for audio_file in audio_files:
            try:
                # Check if file exists and has reasonable size
                if not os.path.exists(audio_file):
                    continue

                file_size = os.path.getsize(audio_file)
                if file_size < 1000:  # Less than 1KB is likely not a real audio file
                    logger.warning(
                        f"File {audio_file} too small ({file_size} bytes), skipping"
                    )
                    continue

                # Check if file starts with HTML content
                # (common when blocked by anti-bot)
                try:
                    with open(audio_file, "rb") as f:
                        first_bytes = f.read(200)

                    # Check for HTML content
                    if (
                        first_bytes.startswith(b"<html")
                        or first_bytes.startswith(b"<!DOCTYPE")
                        or b"<iframe" in first_bytes[:100]
                    ):
                        logger.warning(
                            f"❌ File {audio_file} is HTML (anti-bot protection), "
                            "skipping"
                        )
                        # Show preview for debugging
                        try:
                            preview = first_bytes.decode("utf-8", errors="ignore")[:150]
                            logger.warning(f"HTML preview: {preview}...")
                        except Exception:
                            pass
                        continue

                    # Check for other text-based error responses
                    if (
                        first_bytes.startswith(b"{")
                        and b"error" in first_bytes[:100].lower()
                    ):
                        logger.warning(
                            f"❌ File {audio_file} appears to be JSON error " "response"
                        )
                        continue

                except Exception as e:
                    logger.warning(f"Could not read file header for {audio_file}: {e}")

                # If file is reasonably large and doesn't appear to be an
                # error page, accept it
                if file_size > 50000:  # > 50KB should be valid audio
                    logger.info(
                        f"✅ Found valid audio file: {audio_file} "
                        f"(size: {file_size} bytes)"
                    )
                    return audio_file
                else:
                    logger.warning(
                        f"File {audio_file} might be too small ({file_size} bytes) "
                        "but will try it"
                    )
                    # Still try smaller files as some short audio clips
                    # might be legitimate
                    return audio_file

            except Exception as e:
                logger.warning(f"Error validating {audio_file}: {e}")
                continue

        # If we get here, no valid audio files were found
        file_details = []
        for audio_file in audio_files[:5]:  # Show first 5 files
            try:
                size = (
                    os.path.getsize(audio_file)
                    if os.path.exists(audio_file)
                    else "missing"
                )
                file_details.append(f"{audio_file} ({size} bytes)")
            except Exception:
                file_details.append(f"{audio_file} (error)")

        raise AudioProcessingError(
            f"No valid audio files found. Checked {len(audio_files)} files. "
            f"Details: {file_details}. This usually means BBDown was blocked "
            f"by anti-bot protection. Possible solutions: 1) Try again later, "
            f"2) Use a different network/VPN, 3) Check if BBDown login is "
            f"required for this video."
        )

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
            url: Bilibili video URL

        Returns:
            Dict containing video information
        """
        if not self.validate_url(url):
            raise ValueError(f"Invalid Bilibili URL: {url}")

        bv_id = self.extract_bv_id(url)

        return {
            "bv_id": bv_id,
            "url": url,
            "platform": "bilibili",
            "has_transcripts": False,  # Bilibili doesn't have reliable transcript API
            "note": "Bilibili videos will be processed via audio transcription",
        }
