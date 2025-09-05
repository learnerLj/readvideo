"""Bilibili platform handler."""

import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console

from readvideo.core.audio_processor import AudioProcessor
from readvideo.exceptions import AudioProcessingError, ValidationError, DependencyError
from readvideo.utils import (
    sanitize_filename, extract_bilibili_video_id, detect_file_format,
    managed_temp_directory, cleanup_file_list
)
from readvideo.core.whisper_wrapper import WhisperWrapper

console = Console()
logger = logging.getLogger(__name__)


# Use the common utility function from utils
# detect_audio_format is now available as detect_file_format in utils


def validate_audio_with_ffprobe(
    file_path: str,
) -> Tuple[bool, Optional[float]]:
    """Validate audio file using ffprobe.

    Args:
        file_path: Path to audio file

    Returns:
        Tuple of (is_valid, duration_seconds)
    """
    try:
        import ffmpeg

        # Use ffmpeg.probe to get file info
        probe_data = ffmpeg.probe(file_path)

        # Check if file has audio streams
        streams = probe_data.get("streams", [])
        audio_streams = [s for s in streams if s.get("codec_type") == "audio"]

        if not audio_streams:
            return False, None

        # Get duration
        format_info = probe_data.get("format", {})
        duration = format_info.get("duration")

        if duration:
            duration = float(duration)
            if duration < 0.1:  # Less than 100ms
                return False, None
            return True, duration

        return True, None

    except Exception as e:
        logger.debug(f"ffprobe validation failed for {file_path}: {e}")
        return False, None


class BilibiliHandler:
    """Handler for processing Bilibili videos."""

    def __init__(
        self, 
        whisper_model_path: str = "~/.whisper-models/ggml-large-v3.bin",
        proxy: Optional[str] = None
    ):
        """Initialize Bilibili handler.

        Args:
            whisper_model_path: Path to whisper model for transcription
            proxy: Proxy URL for BBDown and yt-dlp
        """
        self.audio_processor = AudioProcessor()
        self.whisper_wrapper = WhisperWrapper(whisper_model_path)
        self.proxy = proxy
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
        try:
            import yt_dlp  # noqa: F401

            logger.debug("yt-dlp Python library available")
            return True
        except ImportError:
            logger.debug("yt-dlp Python library not available")
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
            re.search(pattern, url, re.IGNORECASE)
            for pattern in bilibili_patterns
        )

    def extract_bv_id(self, url: str) -> Optional[str]:
        """Extract BV ID from Bilibili URL.

        Args:
            url: Bilibili URL

        Returns:
            BV ID or None if not found
        """
        return extract_bilibili_video_id(url)


    def generate_filename(
        self, bv_id: str, video_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate filename based on video title and BV ID.

        Args:
            bv_id: Bilibili BV ID
            video_info: Optional video metadata with title

        Returns:
            Generated filename without extension in format: 标题_BV号
        """
        if not video_info:
            return bv_id

        # Extract title
        title = video_info.get("title", "")

        if not title:
            return bv_id

        # Sanitize title
        # Reserve space for _BV号 (BV号通常12字符，加下划线共13字符)
        max_title_length = 200 - len(bv_id) - 1  # 1 for underscore
        safe_title = sanitize_filename(title, max_title_length)

        # Build filename: 标题_BV号
        filename = f"{safe_title}_{bv_id}"

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
            console.print(
                "🎬 Downloading audio from Bilibili...", style="cyan"
            )
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

            # Use the audio filename format for final output (keeps title and BV ID)
            bv_id = self.extract_bv_id(url) or "bilibili_video"

            if hasattr(result, "get") and result.get("audio_file"):
                audio_filename = os.path.basename(result["audio_file"])
                # Change extension from .m4a/.wav to .txt
                base_name = os.path.splitext(audio_filename)[0]
                final_output = os.path.join(output_dir, f"{base_name}.txt")
            else:
                # Fallback to BV ID only
                final_output = os.path.join(output_dir, f"{bv_id}.txt")

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
        # Create temporary isolated directory for this download
        temp_download_dir = tempfile.mkdtemp(prefix="ytdlp_", dir=output_dir)
        logger.debug(
            f"Created temporary download directory: {temp_download_dir}"
        )

        try:
            import yt_dlp

            # Configure yt-dlp options
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": os.path.join(
                    temp_download_dir, "%(title).200s [%(id)s].%(ext)s"
                ),
                "extractaudio": True,
                "audioformat": "m4a",
                "noplaylist": True,
            }

            # Add proxy support if configured
            if self.proxy:
                ydl_opts["proxy"] = self.proxy
                logger.debug(f"Using proxy for yt-dlp: {self.proxy}")

            # Add Chrome cookies support by default
            ydl_opts["cookiesfrombrowser"] = ("chrome",)
            logger.info("🍪 Using cookies from Chrome browser")

            logger.info("🔄 Attempting download with yt-dlp Python library...")

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Download the audio
                ydl.extract_info(url, download=True)

                # Download completed successfully

                # Find and validate downloaded audio files
                audio_candidates = self._find_audio_candidates(
                    temp_download_dir, tool="yt-dlp"
                )

                if not audio_candidates:
                    # List all files for debugging
                    all_files = os.listdir(temp_download_dir)
                    raise AudioProcessingError(
                        f"No valid audio file found after yt-dlp download. "
                        f"Files in temp dir: {all_files}"
                    )

                # Select the best audio file using enhanced validation
                audio_file = self._select_best_audio_file(audio_candidates)

                # Move file to output directory
                final_path = os.path.join(
                    output_dir, os.path.basename(audio_file)
                )
                if os.path.exists(final_path):
                    # Generate unique name if file exists
                    base, ext = os.path.splitext(os.path.basename(audio_file))
                    counter = 1
                    while os.path.exists(final_path):
                        final_path = os.path.join(
                            output_dir, f"{base}_{counter}{ext}"
                        )
                        counter += 1

                os.rename(audio_file, final_path)
                logger.info(
                    f"✅ Downloaded with yt-dlp: {os.path.basename(final_path)}"
                )
                return final_path

        except ImportError:
            raise AudioProcessingError(
                "yt-dlp library not found. Please install: uv add yt-dlp"
            )
        except Exception as e:
            raise AudioProcessingError(f"yt-dlp download failed: {str(e)}")
        finally:
            # Clean up temporary directory
            try:
                import shutil

                if os.path.exists(temp_download_dir):
                    shutil.rmtree(temp_download_dir)
                    logger.debug(
                        f"Cleaned up temp directory: {temp_download_dir}"
                    )
            except Exception as cleanup_e:
                logger.warning(
                    f"Failed to cleanup temp directory: {cleanup_e}"
                )

    def _download_with_bbdown(self, url: str, output_dir: str) -> str:
        """Download audio from Bilibili using BBDown.

        Args:
            url: Bilibili video URL
            output_dir: Output directory

        Returns:
            Path to downloaded audio file
        """
        # Create temporary isolated directory for this download
        temp_download_dir = tempfile.mkdtemp(prefix="bbdown_", dir=output_dir)
        logger.debug(
            f"Created temporary download directory: {temp_download_dir}"
        )

        try:
            # Build BBDown command (BBDown uses system cookies automatically)
            cmd = ["BBDown", "--audio-only", url]
            
            # Note: BBDown doesn't have direct proxy support via command line
            # For proxy usage, users need to configure system-level proxy
            # or use tools like proxychains

            # Set temporary directory as working directory
            original_dir = os.getcwd()
            os.chdir(temp_download_dir)

            try:
                # Run BBDown and capture output for debugging
                result = subprocess.run(
                    cmd, capture_output=True, text=True, check=True
                )
                logger.debug(f"BBDown stdout: {result.stdout[:500]}...")

                # Find and validate downloaded audio files
                audio_candidates = self._find_audio_candidates(
                    temp_download_dir, tool="bbdown"
                )

                if not audio_candidates:
                    # List all files for debugging
                    all_files = []
                    for root, dirs, files in os.walk(temp_download_dir):
                        for file in files:
                            all_files.append(os.path.join(root, file))
                    logger.error(f"All files found: {all_files}")

                    raise AudioProcessingError(
                        f"No valid audio file found after BBDown download. "
                        f"Found {len(all_files)} files: {all_files[:5]}"
                    )

                # Select the best audio file using enhanced validation
                audio_file = self._select_best_audio_file(audio_candidates)

                # Move file to output directory
                final_path = os.path.join(
                    output_dir, os.path.basename(audio_file)
                )
                if os.path.exists(final_path):
                    # Generate unique name if file exists
                    base, ext = os.path.splitext(os.path.basename(audio_file))
                    counter = 1
                    while os.path.exists(final_path):
                        final_path = os.path.join(
                            output_dir, f"{base}_{counter}{ext}"
                        )
                        counter += 1

                os.rename(audio_file, final_path)
                logger.info(
                    f"✅ Downloaded with BBDown: {os.path.basename(final_path)}"
                )
                return final_path

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
        finally:
            # Clean up temporary directory
            try:
                import shutil

                if os.path.exists(temp_download_dir):
                    shutil.rmtree(temp_download_dir)
                    logger.debug(
                        f"Cleaned up temp directory: {temp_download_dir}"
                    )
            except Exception as cleanup_e:
                logger.warning(
                    f"Failed to cleanup temp directory: {cleanup_e}"
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
                    logger.debug(
                        f"Cleaning up BBDown residual directory: {item_path}"
                    )
                    shutil.rmtree(item_path)
        except Exception as e:
            # Don't fail the whole process if cleanup fails
            logger.debug(f"Failed to cleanup BBDown residuals: {e}")

    def _find_audio_candidates(
        self, search_dir: str, tool: str = "unknown"
    ) -> List[Dict[str, Any]]:
        """Find and analyze potential audio files with enhanced validation.

        Args:
            search_dir: Directory to search in
            tool: Name of the download tool used (for logging)

        Returns:
            List of audio file candidates with metadata
        """
        audio_extensions = [".m4a", ".mp3", ".aac", ".wav", ".flac", ".ogg"]
        candidates = []

        for root, dirs, files in os.walk(search_dir):
            for file in files:
                if any(file.lower().endswith(ext) for ext in audio_extensions):
                    file_path = os.path.join(root, file)

                    # Basic file info
                    try:
                        file_size = os.path.getsize(file_path)
                        mtime = os.path.getmtime(file_path)

                        # Skip obviously invalid files
                        if file_size < 1000:  # Less than 1KB
                            logger.debug(
                                f"Skipping {file}: too small ({file_size} bytes)"
                            )
                            continue

                        # Detect format and validate content
                        detected_format = detect_file_format(file_path)
                        is_valid = detected_format != "unknown"

                        candidate = {
                            "path": file_path,
                            "filename": file,
                            "size": file_size,
                            "mtime": mtime,
                            "detected_format": detected_format,
                            "format_valid": is_valid,
                            "tool": tool,
                        }

                        candidates.append(candidate)
                        logger.debug(
                            f"Found candidate: {file} (size: {file_size}, format: {detected_format}, valid: {is_valid})"
                        )

                    except Exception as e:
                        logger.warning(f"Failed to analyze {file}: {e}")
                        continue

        logger.info(f"Found {len(candidates)} audio candidates from {tool}")
        return candidates

    def _select_best_audio_file(self, candidates: List[Dict[str, Any]]) -> str:
        """Select the first valid audio file from candidates.

        Args:
            candidates: List of audio file candidates with metadata

        Returns:
            Path to a valid audio file

        Raises:
            AudioProcessingError: If no valid audio files found
        """
        if not candidates:
            raise AudioProcessingError("No audio file candidates provided")

        # Find the first file with valid audio format
        for candidate in candidates:
            if candidate["format_valid"]:
                logger.info(
                    f"Selected audio file: {candidate['filename']} "
                    f"(format: {candidate['detected_format']}, size: {candidate['size']} bytes)"
                )
                return str(candidate["path"])

        # If no valid format found, provide detailed error
        error_details = []
        for candidate in candidates[:3]:  # Show top 3 for debugging
            error_details.append(
                f"{candidate['filename']}: {candidate['detected_format'] or 'unknown format'} "
                f"({candidate['size']} bytes)"
            )

        raise AudioProcessingError(
            f"No valid audio files found among {len(candidates)} candidates. "
            f"Files checked: {'; '.join(error_details)}. This usually means the download "
            f"was blocked by anti-bot protection."
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
            audio_file,
            wav_file,
            target_format="wav",
            sample_rate=16000,
            channels=1,
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
