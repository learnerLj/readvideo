"""YouTube channel content processing handler."""

import json
import os
import re
import subprocess
from datetime import datetime
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.progress import Progress

from ..platforms.youtube import YouTubeHandler

console = Console()


class YouTubeUserHandler:
    """Handler for processing all videos from a YouTube channel."""

    def __init__(
        self, 
        whisper_model_path: str = "~/.whisper-models/ggml-large-v3.bin",
        proxy: Optional[str] = None
    ):
        """Initialize user handler.

        Args:
            whisper_model_path: Path to whisper model for transcription
            proxy: Proxy URL for network requests
        """
        self.whisper_model_path = whisper_model_path
        self.proxy = proxy
        self.youtube_handler = YouTubeHandler(whisper_model_path, proxy=proxy)

    def extract_channel_info(self, channel_input: str) -> Dict[str, str]:
        """Extract channel information from URL or username input.

        Args:
            channel_input: Channel username (@username) or channel URL

        Returns:
            Dictionary containing channel identifier and URL

        Raises:
            ValueError: If channel info cannot be extracted
        """
        # Clean up input
        channel_input = channel_input.strip()

        # Handle @username format
        if channel_input.startswith("@"):
            username = channel_input
            channel_url = f"https://www.youtube.com/{username}/videos"
            return {
                "identifier": username,
                "url": channel_url,
                "display_name": username,
            }

        # Handle full URLs
        if "youtube.com" in channel_input:
            # Extract from various URL formats
            patterns = [
                r"youtube\.com/@([^/]+)",  # @username in URL
                r"youtube\.com/c/([^/]+)",  # /c/channelname
                r"youtube\.com/user/([^/]+)",  # /user/username
                r"youtube\.com/channel/([^/]+)",  # /channel/UCxxx
            ]

            for pattern in patterns:
                match = re.search(pattern, channel_input)
                if match:
                    identifier = match.group(1)
                    # Normalize to @username format if possible
                    if pattern.startswith(r"youtube\.com/@"):
                        display_name = f"@{identifier}"
                        channel_url = (
                            f"https://www.youtube.com/@{identifier}/videos"
                        )
                    elif pattern.startswith(r"youtube\.com/channel/"):
                        display_name = identifier
                        channel_url = f"https://www.youtube.com/channel/{identifier}/videos"
                    else:
                        display_name = identifier
                        channel_url = (
                            f"https://www.youtube.com/c/{identifier}/videos"
                        )

                    return {
                        "identifier": display_name,
                        "url": channel_url,
                        "display_name": display_name,
                    }

        # Try as plain username (add @ prefix)
        if re.match(r"^[a-zA-Z0-9_-]+$", channel_input):
            username = f"@{channel_input}"
            channel_url = f"https://www.youtube.com/{username}/videos"
            return {
                "identifier": username,
                "url": channel_url,
                "display_name": username,
            }

        raise ValueError(f"Cannot extract channel info from: {channel_input}")

    def get_channel_videos(
        self,
        channel_url: str,
        start_date: Optional[str] = None,
        max_videos: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get channel's video list with filtering.

        Args:
            channel_url: Channel videos URL
            start_date: Start date filter (YYYY-MM-DD format)
            max_videos: Maximum number of videos to fetch

        Returns:
            List of video information dictionaries
        """
        try:
            # Build yt-dlp command for getting video list
            cmd = [
                "yt-dlp",
                "--flat-playlist",
                "--quiet",
                "--no-warnings",
                "--print",
                "%(id)s|%(title)s|%(upload_date)s",
            ]

            # Note: Date filtering via yt-dlp is unreliable due to YouTube limitations
            # We'll rely on max_videos parameter for limiting instead

            # Add proxy if configured
            if self.proxy:
                cmd.extend(["--proxy", self.proxy])

            cmd.append(channel_url)

            console.print("🔍 Fetching channel videos...", style="cyan")
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True
            )

            videos = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue

                parts = line.split("|", 2)
                if len(parts) >= 3:
                    video_id, title, upload_date = parts

                    # Format date for readability
                    formatted_date = None
                    if upload_date and len(upload_date) == 8:
                        try:
                            formatted_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
                        except (ValueError, IndexError):
                            formatted_date = upload_date

                    video_info = {
                        "video_id": video_id,
                        "title": title,
                        "upload_date": upload_date,
                        "formatted_date": formatted_date,
                        "video_url": f"https://www.youtube.com/watch?v={video_id}",
                    }
                    videos.append(video_info)

            # Apply max_videos limit after fetching
            total_videos = len(videos)
            if max_videos and total_videos > max_videos:
                videos = videos[:max_videos]
                console.print(f"📋 Limited to {max_videos} videos (from {total_videos} total)", style="yellow")

            console.print(f"📋 Found {len(videos)} videos", style="green")
            return videos

        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to fetch channel videos: {e}"
            if e.stderr:
                error_msg += (
                    f"\nError: {e.stderr.decode('utf-8', errors='ignore')}"
                )
            console.print(f"❌ {error_msg}", style="red")
            return []
        except Exception as e:
            console.print(
                f"❌ Error fetching channel videos: {e}", style="red"
            )
            return []

    def create_channel_directory(
        self, output_dir: str, channel_info: Dict[str, str]
    ) -> str:
        """Create channel-specific output directory.

        Args:
            output_dir: Base output directory
            channel_info: Channel information dictionary

        Returns:
            Path to created channel directory
        """
        safe_name = re.sub(r"[^\w\-_.]", "_", channel_info["display_name"])
        channel_dir = os.path.join(output_dir, f"youtube_{safe_name}")

        # Create directory structure
        os.makedirs(channel_dir, exist_ok=True)
        os.makedirs(os.path.join(channel_dir, "transcripts"), exist_ok=True)

        return channel_dir

    def save_video_list(
        self,
        channel_dir: str,
        channel_info: Dict[str, str],
        videos: List[Dict[str, Any]],
    ):
        """Save video list to JSON file.

        Args:
            channel_dir: Channel directory path
            channel_info: Channel information
            videos: List of video information
        """
        video_list_file = os.path.join(channel_dir, "video_list.json")

        data = {
            "channel_info": {**channel_info, "total_videos": len(videos)},
            "videos": videos,
            "generated_at": datetime.now().isoformat(),
        }

        with open(video_list_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        console.print(
            f"💾 Saved video list to: {video_list_file}", style="dim"
        )

    def load_processing_status(self, channel_dir: str) -> Dict[str, List[str]]:
        """Load processing status for resume capability.

        Args:
            channel_dir: Channel directory path

        Returns:
            Dictionary with completed, failed, and skipped video lists
        """
        status_file = os.path.join(channel_dir, "processing_status.json")

        if not os.path.exists(status_file):
            return {"completed": [], "failed": [], "skipped": []}

        try:
            with open(status_file, "r", encoding="utf-8") as f:
                status = json.load(f)
                # Clean up inconsistent states after loading
                return self.cleanup_processing_status(status)
        except Exception as e:
            console.print(
                f"⚠️ Error loading processing status: {e}", style="yellow"
            )
            return {"completed": [], "failed": [], "skipped": []}

    def cleanup_processing_status(
        self, status: Dict[str, List[str]]
    ) -> Dict[str, List[str]]:
        """Clean up inconsistent processing status.

        Ensures videos are only in one status list, prioritizing completed over failed.

        Args:
            status: Raw status dictionary

        Returns:
            Cleaned status dictionary
        """
        # Ensure all required keys exist
        status.setdefault("completed", [])
        status.setdefault("failed", [])
        status.setdefault("skipped", [])

        # Remove duplicates within each list
        status["completed"] = list(set(status["completed"]))
        status["failed"] = list(set(status["failed"]))
        status["skipped"] = list(set(status["skipped"]))

        # Priority: completed > failed
        completed_set = set(status["completed"])
        status["failed"] = [
            vid for vid in status["failed"] if vid not in completed_set
        ]

        return status

    def save_processing_status(
        self, channel_dir: str, status: Dict[str, List[str]]
    ):
        """Save processing status to JSON file.

        Args:
            channel_dir: Channel directory path
            status: Status dictionary to save
        """
        status_file = os.path.join(channel_dir, "processing_status.json")
        cleaned_status = self.cleanup_processing_status(status)

        try:
            with open(status_file, "w", encoding="utf-8") as f:
                json.dump(cleaned_status, f, ensure_ascii=False, indent=2)
        except Exception as e:
            console.print(
                f"⚠️ Error saving processing status: {e}", style="yellow"
            )

    def generate_summary(
        self,
        channel_info: Dict[str, str],
        videos: List[Dict[str, Any]],
        results: List[Dict[str, Any]],
        channel_dir: str,
        run_stats: Dict[str, int],
    ) -> Dict[str, Any]:
        """Generate processing summary.

        Args:
            channel_info: Channel information
            videos: List of videos processed
            results: Processing results
            channel_dir: Channel directory path
            run_stats: Run statistics

        Returns:
            Summary dictionary
        """
        summary = {
            "success": True,
            "channel_info": channel_info,
            "total_videos": len(videos),
            "run_stats": run_stats,
            "output_dir": channel_dir,
            "results": results,
        }

        # Save summary to file
        summary_file = os.path.join(channel_dir, "processing_summary.json")
        try:
            with open(summary_file, "w", encoding="utf-8") as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
        except Exception as e:
            console.print(f"⚠️ Error saving summary: {e}", style="yellow")

        return summary

    async def process_channel(
        self,
        channel_input: str,
        output_dir: str,
        start_date: Optional[str] = None,
        max_videos: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Process all videos from a YouTube channel.

        Args:
            channel_input: Channel username or URL
            output_dir: Output directory for transcripts
            start_date: Start date filter (YYYY-MM-DD format)
            max_videos: Maximum number of videos to process

        Returns:
            Dictionary containing processing results and statistics
        """
        try:
            # Extract channel information
            console.print("🔍 Extracting channel information...", style="cyan")
            channel_info = self.extract_channel_info(channel_input)

            console.print(
                f"📺 Processing channel: {channel_info['display_name']}",
                style="bold cyan",
            )

            # Create channel directory
            channel_dir = self.create_channel_directory(
                output_dir, channel_info
            )
            console.print(f"📁 Output directory: {channel_dir}", style="dim")

            # Get channel videos
            videos = self.get_channel_videos(
                channel_info["url"], start_date, max_videos
            )

            if not videos:
                return {
                    "success": False,
                    "error": "No videos found matching criteria",
                    "channel_info": channel_info,
                }

            # Save video list
            self.save_video_list(channel_dir, channel_info, videos)

            # Load processing status for resume capability
            status = self.load_processing_status(channel_dir)

            # Filter videos that are already completed
            already_completed = len(
                [
                    vid
                    for vid in videos
                    if vid["video_id"] in status["completed"]
                ]
            )

            console.print(
                f"📊 Status: {len(videos)} total videos, "
                f"{already_completed} already completed, "
                f"{len(videos) - already_completed} remaining",
                style="cyan",
            )

            # Process videos
            results = []
            attempted_this_run = 0
            successful_this_run = 0
            failed_this_run = 0
            skipped_this_run = 0

            with Progress() as progress:
                task = progress.add_task(
                    f"Processing {channel_info['display_name']}",
                    total=len(videos),
                )

                for i, video in enumerate(videos):
                    video_id = video["video_id"]

                    # Skip if already processed
                    if video_id in status["completed"]:
                        console.print(
                            f"⏭️ Skipping already processed: {video['title'][:50]}...",
                            style="dim",
                        )
                        skipped_this_run += 1
                        progress.update(task, advance=1)
                        continue

                    attempted_this_run += 1

                    try:
                        console.print(
                            f"\n🎬 Processing ({i+1}/{len(videos)}): {video['title'][:50]}...",
                            style="cyan",
                        )

                        # Process video using existing handler
                        video_url = video["video_url"]
                        result = self.youtube_handler.process(
                            video_url,
                            output_dir=os.path.join(
                                channel_dir, "transcripts"
                            ),
                            cleanup=True,
                        )

                        result["video_info"] = video
                        results.append(result)

                        # Add to completed and remove from failed if it was there
                        if video_id not in status["completed"]:
                            status["completed"].append(video_id)
                        if video_id in status["failed"]:
                            status["failed"].remove(video_id)

                        successful_this_run += 1

                        console.print(
                            f"✅ Completed: {video['title'][:50]}...",
                            style="green",
                        )

                    except Exception as e:
                        console.print(
                            f"❌ Failed to process {video['title'][:50]}...: {e}",
                            style="red",
                        )

                        # Add to failed only if not already completed
                        if (
                            video_id not in status["completed"]
                            and video_id not in status["failed"]
                        ):
                            status["failed"].append(video_id)

                        failed_this_run += 1

                        results.append(
                            {
                                "success": False,
                                "error": str(e),
                                "video_info": video,
                            }
                        )

                    # Save status after each video
                    self.save_processing_status(channel_dir, status)
                    progress.update(task, advance=1)

            # Calculate statistics
            run_stats = {
                "attempted_this_run": attempted_this_run,
                "successful_this_run": successful_this_run,
                "failed_this_run": failed_this_run,
                "skipped_this_run": skipped_this_run,
                "already_completed": already_completed,
                "total_completed": len(status["completed"]),
                "total_failed": len(status["failed"]),
            }

            # Generate final summary
            summary = self.generate_summary(
                channel_info, videos, results, channel_dir, run_stats
            )

            console.print("\n🎉 Processing completed!", style="bold green")
            if attempted_this_run > 0:
                console.print(
                    f"📊 This run: {successful_this_run} successful, "
                    f"{failed_this_run} failed",
                    style="cyan",
                )
            if skipped_this_run > 0:
                console.print(
                    f"⏭️ Skipped: {skipped_this_run} already processed",
                    style="yellow",
                )

            return summary

        except Exception as e:
            console.print(f"❌ Channel processing failed: {e}", style="red")
            return {
                "success": False,
                "error": str(e),
                "channel_input": channel_input,
            }
