"""Supadata API transcript fetcher for YouTube videos."""

import json
import os
import re
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from rich.console import Console

console = Console()


class SupadataFetchError(Exception):
    """Exception raised when Supadata transcript fetching fails."""
    pass


class SupadataTranscriptFetcher:
    """Fetcher for YouTube video transcripts using Supadata API."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize the Supadata transcript fetcher.
        
        Args:
            config_path: Path to config file. Defaults to ~/.readvideo_config.json
        """
        self.config_path = config_path or os.path.expanduser("~/.readvideo_config.json")
        self.config = self._load_config()
        
        # Support both single api_key (backward compatibility) and multiple api_keys
        supadata_config = self.config["apis"]["supadata"]
        if "api_keys" in supadata_config:
            self.api_keys = supadata_config["api_keys"]
        elif "api_key" in supadata_config:
            # Backward compatibility - convert single key to list
            self.api_keys = [supadata_config["api_key"]]
        else:
            raise SupadataFetchError("No API keys found in config. Please add 'api_keys' array or 'api_key' field.")
            
        self.base_url = supadata_config["base_url"]
        self.retry_all_keys = supadata_config.get("retry_all_keys", True)
        self.key_rotation_strategy = supadata_config.get("key_rotation_strategy", "round_robin")
        self.current_key_index = 0
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            raise SupadataFetchError(
                f"Config file not found: {self.config_path}. "
                "Please create ~/.readvideo_config.json with your Supadata API key."
            )
        except json.JSONDecodeError as e:
            raise SupadataFetchError(f"Invalid JSON in config file: {e}")

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

    def _get_next_api_key(self) -> str:
        """Get next API key based on rotation strategy."""
        if self.key_rotation_strategy == "random":
            return random.choice(self.api_keys)
        elif self.key_rotation_strategy == "round_robin":
            key = self.api_keys[self.current_key_index]
            self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
            return key
        else:
            # Default to first key
            return self.api_keys[0]

    def _try_request_with_key(self, api_key: str, api_url: str, params: Dict, timeout: int = 30) -> requests.Response:
        """Try API request with a specific key."""
        headers = {
            'x-api-key': api_key,
            'Content-Type': 'application/json'
        }
        
        response = requests.get(api_url, params=params, headers=headers, timeout=timeout)
        return response

    def fetch_transcript_from_url(self, url: str) -> Dict[str, Any]:
        """Fetch transcript from YouTube URL using Supadata API.
        
        Args:
            url: YouTube URL
            
        Returns:
            Dict containing transcript data and metadata
        """
        console.print(f"🔍 Fetching transcript via Supadata API: {url}", style="cyan")
        
        # Use the transcript endpoint with URL parameter
        api_url = f"{self.base_url}/transcript"
        params = {'url': url}
        
        # Try all keys if retry_all_keys is enabled
        keys_to_try = self.api_keys if self.retry_all_keys else [self._get_next_api_key()]
        last_exception = None
        
        for i, api_key in enumerate(keys_to_try):
            try:
                key_suffix = api_key[-8:] if len(api_key) > 8 else api_key
                if len(keys_to_try) > 1:
                    console.print(f"🔑 Trying API key {i+1}/{len(keys_to_try)} (...{key_suffix})", style="dim")
                
                response = self._try_request_with_key(api_key, api_url, params)
                response.raise_for_status()
                
                data = response.json()
                
                # Convert Supadata format to our standard format
                if 'content' in data and data['content']:
                    # Combine all transcript segments into text
                    text_segments = []
                    for segment in data['content']:
                        if 'text' in segment:
                            text_segments.append(segment['text'].strip())
                    
                    formatted_text = ' '.join(text_segments)
                    
                    video_id = self.extract_video_id(url)
                    
                    result = {
                        "success": True,
                        "text": formatted_text,
                        "video_id": video_id,
                        "transcript_info": {
                            "type": "supadata_api",
                            "language": data.get("lang", "unknown"),
                            "language_code": data.get("lang", "unknown"),
                            "api_key_suffix": key_suffix,
                        },
                        "raw_data": data['content'],
                        "segment_count": len(data['content']),
                        "source": "supadata"
                    }
                    
                    console.print(
                        f"✅ Successfully fetched transcript via Supadata ({len(data['content'])} segments) - Key: ...{key_suffix}",
                        style="green"
                    )
                    
                    return result
                else:
                    raise SupadataFetchError("No transcript content in API response")
                    
            except requests.exceptions.HTTPError as e:
                last_exception = e
                if e.response.status_code == 401:
                    console.print(f"❌ Invalid API key (...{key_suffix})", style="red")
                    if not self.retry_all_keys or i == len(keys_to_try) - 1:
                        raise SupadataFetchError("All API keys invalid. Please check your Supadata API keys in config.")
                elif e.response.status_code == 429:
                    console.print(f"⏳ Rate limit exceeded for key (...{key_suffix})", style="yellow")
                    if not self.retry_all_keys or i == len(keys_to_try) - 1:
                        raise SupadataFetchError("Rate limit exceeded for all keys. Please try again later.")
                elif e.response.status_code == 404:
                    # 404 is not key-specific, no need to try other keys
                    raise SupadataFetchError("Video not found or transcript not available.")
                else:
                    console.print(f"🔄 HTTP error {e.response.status_code} for key (...{key_suffix})", style="yellow")
                    if not self.retry_all_keys or i == len(keys_to_try) - 1:
                        raise SupadataFetchError(f"HTTP error {e.response.status_code}: {e}")
                        
            except (requests.exceptions.RequestException, json.JSONDecodeError, Exception) as e:
                last_exception = e
                console.print(f"🔄 Error with key (...{key_suffix}): {e}", style="yellow")
                if not self.retry_all_keys or i == len(keys_to_try) - 1:
                    raise SupadataFetchError(f"All keys failed. Last error: {e}")
        
        # If we get here, all keys failed
        raise SupadataFetchError(f"All {len(keys_to_try)} API keys failed. Last error: {last_exception}")

    def save_transcript(self, transcript_data: Dict[str, Any], output_file: str) -> None:
        """Save transcript to file.
        
        Args:
            transcript_data: Transcript data from fetch_transcript_from_url
            output_file: Path to output file
        """
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(transcript_data["text"])
                
            key_info = transcript_data.get("transcript_info", {}).get("api_key_suffix", "unknown")
            console.print(f"✅ Transcript saved via Supadata (key: ...{key_info}): {output_file}", style="green")
            
        except Exception as e:
            raise SupadataFetchError(f"Error saving transcript: {e}")