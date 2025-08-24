"""Wrapper for whisper-cli command line tool."""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from rich.console import Console

console = Console()


class WhisperCliError(Exception):
    """Exception raised when whisper-cli encounters an error."""

    pass


class WhisperWrapper:
    """Wrapper for calling whisper-cli command line tool."""

    def __init__(
        self,
        model_path: str = "~/.whisper-models/ggml-large-v3.bin",
        whisper_cli_path: str = "whisper-cli",
    ):
        """Initialize WhisperWrapper.

        Args:
            model_path: Path to the whisper model file
            whisper_cli_path: Path to whisper-cli executable
        """
        self.model_path = os.path.expanduser(model_path)
        self.whisper_cli_path = whisper_cli_path
        self.verify_whisper_cli()
        self.verify_model()

    def verify_whisper_cli(self) -> None:
        """Verify that whisper-cli is available in PATH."""
        if not shutil.which(self.whisper_cli_path):
            raise WhisperCliError(
                f"whisper-cli not found at '{self.whisper_cli_path}'. "
                "Please ensure whisper.cpp is installed and whisper-cli is in PATH."
            )

    def verify_model(self) -> None:
        """Verify that the model file exists."""
        if not os.path.exists(self.model_path):
            raise WhisperCliError(
                f"Model file not found at '{self.model_path}'. "
                "Please ensure the whisper model is downloaded."
            )

    def transcribe(
        self,
        audio_file: str,
        language: Optional[str] = "zh",
        auto_detect: bool = False,
        output_dir: Optional[str] = None,
        silent: bool = False,
    ) -> Dict[str, Any]:
        """Transcribe audio file using whisper-cli.

        Args:
            audio_file: Path to audio file to transcribe
            language: Language code (e.g., 'zh', 'en') or None for auto-detect
            auto_detect: Whether to use auto language detection
            output_dir: Directory to save output files (default: same as input)
            silent: Whether to suppress detailed output (for batch processing)

        Returns:
            Dict containing transcription results and metadata
        """
        if not os.path.exists(audio_file):
            raise FileNotFoundError(f"Audio file not found: {audio_file}")

        # Build command
        cmd = [
            self.whisper_cli_path,
            "-m",
            self.model_path,
            "-otxt",  # output text file
        ]

        # Add language parameter
        if not auto_detect and language:
            cmd.extend(["-l", language])

        # Add output directory if specified
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, Path(audio_file).stem)
            cmd.extend(["-of", output_file])

        cmd.append(audio_file)

        if not silent:
            console.print("🎙️ Transcribing audio...", style="cyan")
            if auto_detect:
                console.print(
                    "🔍 Using automatic language detection...", style="yellow"
                )
            else:
                lang_name = {"zh": "Chinese", "en": "English"}.get(
                    language or "unknown", language or "unknown"
                )
                console.print(
                    f"🌍 Using {lang_name} language recognition...", style="yellow"
                )

        try:
            # Run whisper-cli with appropriate output control
            if silent:
                # Silent mode: capture all output to avoid cluttering during batch
                subprocess.run(cmd, check=True, capture_output=True, text=True)
            else:
                # Single video mode: allow normal output for user to see progress
                subprocess.run(cmd, check=True, text=True)

            # Find output text file
            output_txt_file = self._find_output_file(audio_file, output_dir)

            if not output_txt_file or not os.path.exists(output_txt_file):
                raise WhisperCliError(
                    "Transcription completed but output file not found"
                )

            # Read transcription text
            with open(output_txt_file, "r", encoding="utf-8") as f:
                transcription_text = f.read().strip()

            return {
                "success": True,
                "text": transcription_text,
                "output_file": output_txt_file,
                "language": language if not auto_detect else "auto",
                "audio_file": audio_file,
            }

        except subprocess.CalledProcessError as e:
            error_msg = f"whisper-cli failed with exit code {e.returncode}"
            if e.stderr:
                error_msg += f": {e.stderr}"
            raise WhisperCliError(error_msg)

    def _find_output_file(
        self, audio_file: str, output_dir: Optional[str] = None
    ) -> Optional[str]:
        """Find the output text file generated by whisper-cli.

        Args:
            audio_file: Original audio file path
            output_dir: Output directory if specified

        Returns:
            Path to output text file or None if not found
        """
        base_name = Path(audio_file).stem

        # Check possible output locations
        possible_paths = []

        if output_dir:
            possible_paths.append(os.path.join(output_dir, f"{base_name}.txt"))

        # Default behavior: same directory as input file
        audio_dir = os.path.dirname(audio_file)
        possible_paths.extend(
            [
                os.path.join(
                    audio_dir, f"{base_name}.wav.txt"
                ),  # whisper-cli often appends .wav.txt
                os.path.join(audio_dir, f"{base_name}.txt"),
                f"{audio_file}.txt",  # Sometimes appends to full filename
            ]
        )

        for path in possible_paths:
            if os.path.exists(path):
                return path

        return None

    def cleanup_temp_files(
        self, audio_file: str, keep_transcription: bool = True
    ) -> None:
        """Clean up temporary files created during transcription.

        Args:
            audio_file: Original audio file path
            keep_transcription: Whether to keep the transcription text file
        """
        base_name = Path(audio_file).stem
        audio_dir = os.path.dirname(audio_file)

        # Files to potentially clean up
        temp_files = [
            os.path.join(audio_dir, f"{base_name}.wav"),  # Converted wav file
            os.path.join(audio_dir, f"{base_name}_temp.m4a"),  # Temp audio from video
        ]

        if not keep_transcription:
            temp_files.extend(
                [
                    os.path.join(audio_dir, f"{base_name}.wav.txt"),
                    os.path.join(audio_dir, f"{base_name}.txt"),
                    f"{audio_file}.txt",
                ]
            )

        for file_path in temp_files:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    console.print(
                        f"🗑️ Cleaning temporary file: {os.path.basename(file_path)}",
                        style="dim",
                    )
                except OSError:
                    pass  # Ignore cleanup errors
