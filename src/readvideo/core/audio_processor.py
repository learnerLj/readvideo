"""Audio processing utilities using ffmpeg."""

import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Dict, List, Optional

from rich.console import Console

console = Console()


class AudioProcessingError(Exception):
    """Exception raised when audio processing fails."""

    pass


class AudioProcessor:
    """Audio processor for format conversion and extraction."""

    def __init__(self):
        """Initialize audio processor."""
        self.supported_audio_formats = {
            "mp3",
            "m4a",
            "wav",
            "flac",
            "ogg",
            "aac",
            "wma",
        }
        self.supported_video_formats = {
            "mp4",
            "mkv",
            "avi",
            "mov",
            "wmv",
            "flv",
            "webm",
            "m4v",
        }
        self.verify_ffmpeg()

    def verify_ffmpeg(self) -> None:
        """Verify that ffmpeg is available."""
        if not shutil.which("ffmpeg"):
            console.print(
                "⚠️ Warning: ffmpeg not found. Video processing may be limited.",
                style="yellow",
            )

    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """Get information about audio/video file.

        Args:
            file_path: Path to media file

        Returns:
            Dict containing file information
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        path = Path(file_path)
        extension = path.suffix.lower().lstrip(".")

        file_info = {
            "path": file_path,
            "name": path.name,
            "stem": path.stem,
            "extension": extension,
            "size": os.path.getsize(file_path),
            "is_audio": extension in self.supported_audio_formats,
            "is_video": extension in self.supported_video_formats,
            "is_supported": extension
            in (self.supported_audio_formats | self.supported_video_formats),
        }

        return file_info

    def extract_audio_from_video(
        self,
        video_file: str,
        output_file: Optional[str] = None,
        audio_format: str = "m4a",
    ) -> str:
        """Extract audio from video file using ffmpeg.

        Args:
            video_file: Path to video file
            output_file: Path for output audio file (optional)
            audio_format: Output audio format

        Returns:
            Path to extracted audio file
        """
        if not os.path.exists(video_file):
            raise FileNotFoundError(f"Video file not found: {video_file}")

        file_info = self.get_file_info(video_file)
        if not file_info["is_video"]:
            raise AudioProcessingError(
                f"File is not a supported video format: {video_file}"
            )

        # Generate output filename if not provided
        if output_file is None:
            video_path = Path(video_file)
            output_file = str(
                video_path.parent / f"{video_path.stem}_temp.{audio_format}"
            )

        console.print("🔄 Extracting audio track...", style="cyan")

        try:
            # Use ffmpeg to extract audio
            cmd = [
                "ffmpeg",
                "-hide_banner",  # Hide version info
                "-i",
                video_file,
                "-vn",  # No video
                "-acodec",
                "copy",  # Copy audio codec when possible
                "-y",  # Overwrite output file
                output_file,
            ]

            subprocess.run(cmd, check=True)

            if os.path.exists(output_file):
                console.print(
                    f"📁 Audio extraction completed: {os.path.basename(output_file)}",
                    style="green",
                )
                return output_file
            else:
                raise AudioProcessingError(
                    "Audio extraction completed but output file not found"
                )

        except subprocess.CalledProcessError as e:
            error_msg = f"ffmpeg failed with exit code {e.returncode}"
            if e.stderr:
                error_msg += f": {e.stderr}"
            raise AudioProcessingError(error_msg)
        except FileNotFoundError:
            raise AudioProcessingError(
                "ffmpeg not found. Please install ffmpeg to extract audio from videos."
            )

    def convert_audio_format(
        self,
        input_file: str,
        output_file: str,
        target_format: str = "wav",
        sample_rate: int = 16000,
        channels: int = 1,
    ) -> str:
        """Convert audio file format using ffmpeg.

        Args:
            input_file: Path to input audio file
            output_file: Path for output file
            target_format: Target audio format
            sample_rate: Target sample rate in Hz
            channels: Number of audio channels (1=mono, 2=stereo)

        Returns:
            Path to converted audio file
        """
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"Audio file not found: {input_file}")

        console.print("🔄 Converting audio format...", style="cyan")

        try:
            # Build ffmpeg command for audio conversion
            cmd = [
                "ffmpeg",
                "-hide_banner",  # Hide version info
                "-i",
                input_file,
                "-ar",
                str(sample_rate),  # Sample rate
                "-ac",
                str(channels),  # Number of channels
                "-y",  # Overwrite output file
            ]

            # Add format-specific options
            if target_format == "wav":
                cmd.extend(["-c:a", "pcm_s16le"])  # PCM 16-bit little-endian
            elif target_format == "mp3":
                cmd.extend(["-c:a", "libmp3lame", "-b:a", "128k"])
            elif target_format == "m4a":
                cmd.extend(["-c:a", "aac", "-b:a", "128k"])

            cmd.append(output_file)

            subprocess.run(cmd, check=True)

            if os.path.exists(output_file):
                console.print(
                    f"✅ Audio conversion completed: {os.path.basename(output_file)}",
                    style="green",
                )
                return output_file
            else:
                raise AudioProcessingError(
                    "Audio conversion completed but output file not found"
                )

        except subprocess.CalledProcessError as e:
            error_msg = f"ffmpeg conversion failed with exit code {e.returncode}"
            if e.stderr:
                error_msg += f": {e.stderr}"
            raise AudioProcessingError(error_msg)
        except FileNotFoundError:
            raise AudioProcessingError(
                "ffmpeg not found. Please install ffmpeg to convert audio formats."
            )

    def process_media_file(
        self,
        input_file: str,
        target_format: str = "wav",
        output_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process media file (audio/video) for transcription.

        Args:
            input_file: Path to input media file
            target_format: Target audio format for transcription
            output_dir: Output directory (optional)

        Returns:
            Dict containing processing results
        """
        file_info = self.get_file_info(input_file)

        if not file_info["is_supported"]:
            raise AudioProcessingError(
                f"Unsupported file format: {file_info['extension']}\n"
                f"Supported audio formats: {', '.join(self.supported_audio_formats)}\n"
                f"Supported video formats: {', '.join(self.supported_video_formats)}"
            )

        # Determine output directory
        if output_dir is None:
            output_dir = os.path.dirname(input_file)
        else:
            os.makedirs(output_dir, exist_ok=True)

        # Generate output filename
        base_name = file_info["stem"]
        output_file = os.path.join(output_dir, f"{base_name}.{target_format}")

        temp_files = []
        final_audio_file = None

        try:
            if file_info["is_audio"]:
                console.print(
                    f"🎵 Processing audio file: {file_info['name']}", style="cyan"
                )

                if file_info["extension"] == target_format:
                    # Already in target format
                    final_audio_file = input_file
                else:
                    # Convert audio format
                    final_audio_file = self.convert_audio_format(
                        input_file, output_file, target_format
                    )
                    temp_files.append(final_audio_file)

            elif file_info["is_video"]:
                console.print(
                    f"🎬 Processing video file: {file_info['name']}", style="cyan"
                )

                # Extract audio from video
                temp_audio = os.path.join(output_dir, f"{base_name}_temp.m4a")
                extracted_audio = self.extract_audio_from_video(input_file, temp_audio)
                temp_files.append(extracted_audio)

                # Convert to target format if needed
                if target_format != "m4a":
                    final_audio_file = self.convert_audio_format(
                        extracted_audio, output_file, target_format
                    )
                    temp_files.append(final_audio_file)
                else:
                    final_audio_file = extracted_audio

            return {
                "success": True,
                "input_file": input_file,
                "output_file": final_audio_file,
                "file_info": file_info,
                "temp_files": temp_files,
                "target_format": target_format,
            }

        except Exception as e:
            # Clean up temp files on error
            self.cleanup_temp_files(temp_files)
            raise AudioProcessingError(f"Media processing failed: {e}")

    def cleanup_temp_files(self, file_list: List[str]) -> None:
        """Clean up temporary files.

        Args:
            file_list: List of file paths to remove
        """
        for file_path in file_list:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    console.print(
                        f"🗑️ Cleaning temporary file: {os.path.basename(file_path)}",
                        style="dim",
                    )
                except OSError:
                    pass  # Ignore cleanup errors

    def get_audio_duration(self, audio_file: str) -> float:
        """Get duration of audio file in seconds using ffmpeg.

        Args:
            audio_file: Path to audio file

        Returns:
            Duration in seconds
        """
        try:
            cmd = [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                audio_file,
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)

            duration = float(data["format"]["duration"])
            return duration

        except subprocess.CalledProcessError:
            # Fallback: try with ffmpeg
            try:
                cmd = [
                    "ffmpeg",
                    "-hide_banner",
                    "-i",
                    audio_file,
                    "-f",
                    "null",
                    "-",
                    "-v",
                    "quiet",
                    "-stats",
                ]
                subprocess.run(cmd, capture_output=True, text=True, check=True)
                # This is a fallback, return a reasonable default
                return 1.0
            except Exception:
                raise AudioProcessingError(
                    "Failed to get audio duration: ffprobe/ffmpeg failed"
                )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            raise AudioProcessingError(f"Failed to parse audio duration: {e}")
        except FileNotFoundError:
            raise AudioProcessingError(
                "ffprobe not found. Please install ffmpeg package."
            )

    def validate_audio_for_transcription(self, audio_file: str) -> bool:
        """Validate that audio file is suitable for transcription.

        Args:
            audio_file: Path to audio file

        Returns:
            True if audio is valid for transcription
        """
        try:
            duration = self.get_audio_duration(audio_file)
            file_size = os.path.getsize(audio_file)

            # Basic validations
            if duration < 0.1:  # Less than 100ms
                raise AudioProcessingError("Audio file is too short for transcription")

            if file_size < 1024:  # Less than 1KB
                raise AudioProcessingError(
                    "Audio file appears to be empty or corrupted"
                )

            return True

        except Exception as e:
            raise AudioProcessingError(f"Audio validation failed: {e}")
