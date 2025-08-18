"""Bilibili platform handler."""

import os
import re
import subprocess
from typing import Optional, Dict, Any, List
from pathlib import Path

from ..core.audio_processor import AudioProcessor, AudioProcessingError
from ..core.whisper_wrapper import WhisperWrapper, WhisperCliError
from rich.console import Console

console = Console()


class BilibiliHandler:
    """Handler for processing Bilibili videos."""
    
    def __init__(
        self, 
        whisper_model_path: str = "~/.whisper-models/ggml-large-v3.bin"
    ):
        """Initialize Bilibili handler.
        
        Args:
            whisper_model_path: Path to whisper model for transcription
        """
        self.audio_processor = AudioProcessor()
        self.whisper_wrapper = WhisperWrapper(whisper_model_path)
        self.verify_bbdown()
    
    def verify_bbdown(self) -> None:
        """Verify that BBDown is available."""
        import shutil
        if not shutil.which('BBDown'):
            console.print(
                "⚠️ Warning: BBDown not found. Bilibili processing may not work.", 
                style="yellow"
            )
    
    def validate_url(self, url: str) -> bool:
        """Validate that URL is a Bilibili URL.
        
        Args:
            url: URL to validate
            
        Returns:
            True if valid Bilibili URL
        """
        bilibili_patterns = [
            r'bilibili\.com',
            r'b23\.tv',
            r'm\.bilibili\.com'
        ]
        
        return any(re.search(pattern, url, re.IGNORECASE) for pattern in bilibili_patterns)
    
    def extract_bv_id(self, url: str) -> Optional[str]:
        """Extract BV ID from Bilibili URL.
        
        Args:
            url: Bilibili URL
            
        Returns:
            BV ID or None if not found
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
        sanitized = re.sub(invalid_chars, '_', filename)
        
        # Remove multiple consecutive underscores/spaces
        sanitized = re.sub(r'[_\s]+', '_', sanitized)
        
        # Remove leading/trailing underscores
        sanitized = sanitized.strip('_')
        
        # Truncate if too long, but try to keep word boundaries
        if len(sanitized) > max_length:
            truncated = sanitized[:max_length]
            # Try to end at a word boundary
            last_underscore = truncated.rfind('_')
            if last_underscore > max_length * 0.7:  # If underscore is in the last 30%
                truncated = truncated[:last_underscore]
            sanitized = truncated.rstrip('_')
        
        # Ensure not empty
        return sanitized if sanitized else "video"
    
    def generate_filename(self, bv_id: str, video_info: Optional[Dict[str, Any]] = None) -> str:
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
        date = video_info.get('created_date', '')
        title = video_info.get('title', '')
        
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
        video_info: Optional[Dict[str, Any]] = None
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
                silent=silent
            )
            
            # Generate filename based on video info
            bv_id = self.extract_bv_id(url) or "bilibili_video"
            filename = self.generate_filename(bv_id, video_info)
            final_output = os.path.join(output_dir, f"{filename}.txt")
            
            # Copy transcription to final location
            if os.path.exists(result["output_file"]) and result["output_file"] != final_output:
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
                "temp_files": temp_files if not cleanup else []
            }
            
        except Exception as e:
            if cleanup:
                self.audio_processor.cleanup_temp_files(temp_files)
            raise
        finally:
            if cleanup:
                self.audio_processor.cleanup_temp_files(temp_files)
    
    def _download_audio(self, url: str, output_dir: str) -> str:
        """Download audio from Bilibili using BBDown.
        
        Args:
            url: Bilibili video URL
            output_dir: Output directory
            
        Returns:
            Path to downloaded audio file
        """
        try:
            # Build BBDown command
            cmd = [
                'BBDown',
                '--audio-only',
                url
            ]
            
            # Set output directory
            original_dir = os.getcwd()
            os.chdir(output_dir)
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                
                # Find downloaded audio file (BBDown creates m4a files without brackets)
                m4a_files = [f for f in os.listdir('.') 
                           if f.endswith('.m4a') and not f.endswith('].m4a')]
                
                if not m4a_files:
                    raise AudioProcessingError("No audio file found after BBDown download")
                
                # Get the most recent file
                audio_file = max(m4a_files, key=os.path.getctime)
                return os.path.join(output_dir, audio_file)
                
            finally:
                os.chdir(original_dir)
                
        except subprocess.CalledProcessError as e:
            error_msg = f"BBDown failed with exit code {e.returncode}"
            if e.stderr:
                error_msg += f": {e.stderr}"
            raise AudioProcessingError(error_msg)
        except FileNotFoundError:
            raise AudioProcessingError(
                "BBDown not found. Please install BBDown to download from Bilibili."
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
            channels=1
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
            "note": "Bilibili videos will be processed via audio transcription"
        }