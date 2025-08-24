"""Local media file handler."""

import os
from typing import Any, Dict, List, Optional

from rich.console import Console

from ..core.audio_processor import AudioProcessingError, AudioProcessor
from ..core.whisper_wrapper import WhisperWrapper

console = Console()


class LocalMediaHandler:
    """Handler for processing local audio and video files."""

    def __init__(
        self, whisper_model_path: str = "~/.whisper-models/ggml-large-v3.bin"
    ):
        """Initialize local media handler.

        Args:
            whisper_model_path: Path to whisper model for transcription
        """
        self.audio_processor = AudioProcessor()
        self.whisper_wrapper = WhisperWrapper(whisper_model_path)

    def validate_file(self, file_path: str) -> bool:
        """Validate that file exists and is a supported media format.

        Args:
            file_path: Path to media file

        Returns:
            True if file is valid and supported
        """
        if not os.path.exists(file_path):
            return False

        try:
            file_info = self.audio_processor.get_file_info(file_path)
            return file_info["is_supported"]
        except Exception:
            return False

    def process(
        self,
        file_path: str,
        auto_detect: bool = False,
        output_dir: Optional[str] = None,
        cleanup: bool = True,
    ) -> Dict[str, Any]:
        """Process local media file.

        Args:
            file_path: Path to media file
            auto_detect: Whether to use auto language detection for whisper
            output_dir: Output directory for files (default: same as input)
            cleanup: Whether to clean up temporary files

        Returns:
            Dict containing processing results
        """
        if not self.validate_file(file_path):
            raise FileNotFoundError(
                f"File not found or unsupported format: {file_path}"
            )

        file_path = os.path.abspath(file_path)
        file_info = self.audio_processor.get_file_info(file_path)

        console.print(
            f"📁 Processing local file: {file_info['name']}", style="cyan"
        )

        # Set up output directory
        if output_dir is None:
            output_dir = os.path.dirname(file_path)
        else:
            os.makedirs(output_dir, exist_ok=True)

        temp_files: list[str] = []

        try:
            if file_info["is_audio"]:
                return self._process_audio_file(
                    file_path,
                    file_info,
                    auto_detect,
                    output_dir,
                    cleanup,
                    temp_files,
                )
            elif file_info["is_video"]:
                return self._process_video_file(
                    file_path,
                    file_info,
                    auto_detect,
                    output_dir,
                    cleanup,
                    temp_files,
                )
            else:
                raise AudioProcessingError(
                    f"Unsupported file format: {file_info['extension']}"
                )

        except Exception:
            if cleanup:
                self.audio_processor.cleanup_temp_files(temp_files)
            raise
        finally:
            if cleanup and temp_files:
                self.audio_processor.cleanup_temp_files(temp_files)

    def _process_audio_file(
        self,
        file_path: str,
        file_info: Dict[str, Any],
        auto_detect: bool,
        output_dir: str,
        cleanup: bool,
        temp_files: list,
    ) -> Dict[str, Any]:
        """Process audio file for transcription.

        Args:
            file_path: Path to audio file
            file_info: File information from audio_processor
            auto_detect: Whether to use auto language detection
            output_dir: Output directory
            cleanup: Whether to cleanup temp files
            temp_files: List to track temporary files

        Returns:
            Dict containing processing results
        """
        console.print(
            f"🎵 Processing audio file: {file_info['name']}", style="cyan"
        )

        # Validate audio for transcription
        self.audio_processor.validate_audio_for_transcription(file_path)

        # Get audio duration for display
        try:
            duration = self.audio_processor.get_audio_duration(file_path)
            console.print(
                f"⏱️ Audio duration: {duration:.1f} seconds", style="dim"
            )
        except Exception:
            console.print("⏱️ Unable to get audio duration", style="dim")

        # Convert to WAV if needed
        if file_info["extension"] in [
            "mp3",
            "m4a",
            "wav",
            "flac",
            "ogg",
            "aac",
        ]:
            wav_file = os.path.join(output_dir, f"{file_info['stem']}.wav")

            if file_info["extension"] == "wav":
                # Already WAV, use original file
                audio_file_for_transcription = file_path
            else:
                # Convert to WAV
                audio_file_for_transcription = (
                    self.audio_processor.convert_audio_format(
                        file_path,
                        wav_file,
                        target_format="wav",
                        sample_rate=16000,
                        channels=1,
                    )
                )
                temp_files.append(audio_file_for_transcription)
        else:
            raise AudioProcessingError(
                f"Unsupported audio format: {file_info['extension']}"
            )

        # Transcribe with whisper-cli
        language = None if auto_detect else "zh"
        result = self.whisper_wrapper.transcribe(
            audio_file_for_transcription,
            language=language,
            auto_detect=auto_detect,
            output_dir=output_dir,
        )

        # Generate final output filename
        final_output = os.path.join(output_dir, f"{file_info['stem']}.txt")

        # Move transcription to final location if needed
        if (
            os.path.exists(result["output_file"])
            and result["output_file"] != final_output
        ):
            os.rename(result["output_file"], final_output)
            result["output_file"] = final_output

        return {
            "success": True,
            "method": "transcription",
            "platform": "local",
            "file_type": "audio",
            "input_file": file_path,
            "output_file": final_output,
            "text": result["text"],
            "language": result["language"],
            "file_info": file_info,
            "temp_files": temp_files if not cleanup else [],
        }

    def _process_video_file(
        self,
        file_path: str,
        file_info: Dict[str, Any],
        auto_detect: bool,
        output_dir: str,
        cleanup: bool,
        temp_files: list,
    ) -> Dict[str, Any]:
        """Process video file by extracting audio and transcribing.

        Args:
            file_path: Path to video file
            file_info: File information from audio_processor
            auto_detect: Whether to use auto language detection
            output_dir: Output directory
            cleanup: Whether to cleanup temp files
            temp_files: List to track temporary files

        Returns:
            Dict containing processing results
        """
        console.print(
            f"🎬 Processing video file: {file_info['name']}", style="cyan"
        )

        # Extract audio from video
        temp_audio = os.path.join(output_dir, f"{file_info['stem']}_temp.m4a")
        extracted_audio = self.audio_processor.extract_audio_from_video(
            file_path, temp_audio
        )
        temp_files.append(extracted_audio)

        # Convert to WAV for whisper
        wav_file = os.path.join(output_dir, f"{file_info['stem']}.wav")
        wav_audio = self.audio_processor.convert_audio_format(
            extracted_audio,
            wav_file,
            target_format="wav",
            sample_rate=16000,
            channels=1,
        )
        temp_files.append(wav_audio)

        # Transcribe with whisper-cli
        language = None if auto_detect else "zh"
        result = self.whisper_wrapper.transcribe(
            wav_audio,
            language=language,
            auto_detect=auto_detect,
            output_dir=output_dir,
        )

        # Generate final output filename
        final_output = os.path.join(output_dir, f"{file_info['stem']}.txt")

        # Move transcription to final location if needed
        if (
            os.path.exists(result["output_file"])
            and result["output_file"] != final_output
        ):
            os.rename(result["output_file"], final_output)
            result["output_file"] = final_output

        return {
            "success": True,
            "method": "transcription",
            "platform": "local",
            "file_type": "video",
            "input_file": file_path,
            "output_file": final_output,
            "text": result["text"],
            "language": result["language"],
            "file_info": file_info,
            "extracted_audio": extracted_audio,
            "temp_files": temp_files if not cleanup else [],
        }

    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """Get detailed information about a media file.

        Args:
            file_path: Path to media file

        Returns:
            Dict containing file information
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        file_info = self.audio_processor.get_file_info(file_path)

        # Add additional info for audio files
        if file_info["is_audio"]:
            try:
                duration = self.audio_processor.get_audio_duration(file_path)
                file_info["duration_seconds"] = duration
                file_info["duration_formatted"] = self._format_duration(
                    duration
                )
            except Exception:
                file_info["duration_seconds"] = None
                file_info["duration_formatted"] = "Unknown"

        return file_info

    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to human readable format.

        Args:
            seconds: Duration in seconds

        Returns:
            Formatted duration string
        """
        if seconds < 60:
            return f"{seconds:.1f} seconds"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            remaining_seconds = seconds % 60
            return f"{minutes}m {remaining_seconds:.0f}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"

    def list_supported_formats(self) -> Dict[str, List[str]]:
        """Get list of supported file formats.

        Returns:
            Dict with supported audio and video formats
        """
        return {
            "audio_formats": list(
                self.audio_processor.supported_audio_formats
            ),
            "video_formats": list(
                self.audio_processor.supported_video_formats
            ),
        }
