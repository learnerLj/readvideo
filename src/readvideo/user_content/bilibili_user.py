"""Bilibili user content processing handler."""

import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import bilibili_api
from rich.console import Console
from rich.progress import Progress

from ..platforms.bilibili import BilibiliHandler

console = Console()


class BilibiliUserHandler:
    """Handler for processing all videos from a Bilibili user."""

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
        self.bilibili_handler = BilibiliHandler(whisper_model_path, proxy=proxy)

    def extract_uid(self, user_input: str) -> int:
        """Extract UID from URL or direct UID input.

        Args:
            user_input: User UID or space URL

        Returns:
            User UID as integer

        Raises:
            ValueError: If UID cannot be extracted
        """
        # Direct UID
        if user_input.isdigit():
            return int(user_input)

        # URL patterns for Bilibili user space
        patterns = [
            r"space\.bilibili\.com/(\d+)",
            r"bilibili\.com/(\d+)",
            r"/(\d+)/?$",
        ]

        for pattern in patterns:
            match = re.search(pattern, user_input)
            if match:
                return int(match.group(1))

        raise ValueError(f"Cannot extract UID from: {user_input}")

    async def get_user_info(self, uid: int) -> Dict[str, Any]:
        """Get user basic information.

        Args:
            uid: User ID

        Returns:
            Dictionary containing user information
        """
        try:
            user = bilibili_api.user.User(uid)
            user_info = await user.get_relation_info()

            return {
                "uid": uid,
                "name": user_info.get("name", f"User_{uid}"),
                "follower": user_info.get("follower", 0),
                "following": user_info.get("following", 0),
            }
        except Exception as e:
            console.print(
                f"❌ Failed to get user info for UID {uid}: {e}", style="red"
            )
            return {
                "uid": uid,
                "name": f"User_{uid}",
                "follower": 0,
                "following": 0,
            }

    async def get_user_videos(
        self,
        uid: int,
        start_date: Optional[str] = None,
        max_videos: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get user's video list with filtering.

        Args:
            uid: User ID
            start_date: Start date filter (YYYY-MM-DD format)
            max_videos: Maximum number of videos to return

        Returns:
            List of video information dictionaries
        """
        try:
            user = bilibili_api.user.User(uid)
            all_videos = []
            page = 1

            console.print(
                f"🔍 Fetching videos for user {uid}...", style="cyan"
            )

            # Parse start date if provided
            start_timestamp = None
            end_timestamp = None
            if start_date:
                try:
                    from .utils import parse_date_to_timestamp_range

                    start_timestamp, end_timestamp = (
                        parse_date_to_timestamp_range(start_date)
                    )
                    console.print(
                        f"📅 Date filter: videos from {start_date} (inclusive)",
                        style="dim",
                    )
                except ValueError as e:
                    console.print(
                        f"⚠️ {e}, ignoring date filter",
                        style="yellow",
                    )

            # Fetch all videos with pagination
            while True:
                try:
                    video_data = await user.get_videos(pn=page, ps=30)
                    videos = video_data.get("list", {}).get("vlist", [])

                    if not videos:
                        break

                    # Filter by date if specified
                    for video in videos:
                        if start_timestamp:
                            video_created = video.get("created", 0)
                            # Video must be created on or after the start date
                            if video_created < start_timestamp:
                                continue

                        # Add formatted date and URL
                        video["created_date"] = datetime.fromtimestamp(
                            video.get("created", 0)
                        ).strftime("%Y-%m-%d")
                        video["video_url"] = (
                            f"https://www.bilibili.com/video/{video['bvid']}"
                        )

                        all_videos.append(video)

                    console.print(
                        f"📄 Fetched page {page}, total videos: {len(all_videos)}",
                        style="dim",
                    )
                    page += 1

                    # Stop if we've reached the date limit or max videos
                    if (
                        start_timestamp
                        and videos
                        and videos[-1].get("created", 0) < start_timestamp
                    ):
                        # All remaining videos will be older than start_date
                        break
                    if max_videos and len(all_videos) >= max_videos:
                        break

                except Exception as e:
                    console.print(
                        f"⚠️ Error fetching page {page}: {e}", style="yellow"
                    )
                    break

            # Apply max_videos limit
            if max_videos and len(all_videos) > max_videos:
                all_videos = all_videos[:max_videos]

            console.print(
                f"✅ Found {len(all_videos)} videos to process", style="green"
            )
            return all_videos

        except Exception as e:
            console.print(
                f"❌ Failed to get videos for user {uid}: {e}", style="red"
            )
            return []

    def create_user_directory(
        self, output_dir: str, user_info: Dict[str, Any]
    ) -> str:
        """Create user-specific output directory.

        Args:
            output_dir: Base output directory
            user_info: User information dictionary

        Returns:
            Path to created user directory
        """
        safe_name = re.sub(r"[^\w\-_.]", "_", user_info["name"])
        user_dir = os.path.join(output_dir, f"{safe_name}_{user_info['uid']}")

        # Create directory structure
        os.makedirs(user_dir, exist_ok=True)
        os.makedirs(os.path.join(user_dir, "transcripts"), exist_ok=True)

        return user_dir

    def save_video_list(
        self,
        user_dir: str,
        user_info: Dict[str, Any],
        videos: List[Dict[str, Any]],
    ):
        """Save video list to JSON file.

        Args:
            user_dir: User directory path
            user_info: User information
            videos: List of video information
        """
        video_list_file = os.path.join(user_dir, "video_list.json")

        data = {
            "user_info": {**user_info, "total_videos": len(videos)},
            "videos": videos,
            "generated_at": datetime.now().isoformat(),
        }

        with open(video_list_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        console.print(
            f"💾 Saved video list to: {video_list_file}", style="dim"
        )

    def load_processing_status(self, user_dir: str) -> Dict[str, List[str]]:
        """Load processing status for resume capability.

        Args:
            user_dir: User directory path

        Returns:
            Dictionary with completed, failed, and skipped video lists
        """
        status_file = os.path.join(user_dir, "processing_status.json")

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
        # Remove any video from failed list if it's in completed list
        completed_set = set(status["completed"])
        status["failed"] = [
            vid for vid in status["failed"] if vid not in completed_set
        ]

        # Log cleanup if necessary
        original_failed_count = len(status.get("failed", [])) + len(
            completed_set.intersection(set(status.get("failed", [])))
        )
        if original_failed_count != len(status["failed"]):
            console.print(
                f"🧹 Cleaned up {original_failed_count - len(status['failed'])} "
                "inconsistent status entries",
                style="dim",
            )

        return status

    def save_processing_status(self, user_dir: str, status: Dict[str, Any]):
        """Save processing status.

        Args:
            user_dir: User directory path
            status: Status dictionary
        """
        status_file = os.path.join(user_dir, "processing_status.json")

        status["last_update"] = datetime.now().isoformat()

        with open(status_file, "w", encoding="utf-8") as f:
            json.dump(status, f, ensure_ascii=False, indent=2)

    async def process_user(
        self,
        user_input: str,
        output_dir: str,
        start_date: Optional[str] = None,
        max_videos: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Process all videos from a user asynchronously.

        Args:
            user_input: User UID or space URL
            output_dir: Output directory (required)
            start_date: Start date filter (YYYY-MM-DD)
            max_videos: Maximum number of videos to process

        Returns:
            Processing results summary
        """

        try:
            # Extract UID
            uid = self.extract_uid(user_input)
            console.print(f"🎯 Processing user: {uid}", style="bold cyan")

            # Get user info
            user_info = await self.get_user_info(uid)
            console.print(
                f"👤 User: {user_info['name']} (Followers: {user_info['follower']})",
                style="cyan",
            )

            # Create user directory
            user_dir = self.create_user_directory(output_dir, user_info)
            console.print(f"📁 Output directory: {user_dir}", style="cyan")

            # Get videos
            videos = await self.get_user_videos(uid, start_date, max_videos)
            if not videos:
                console.print(
                    "❌ No videos found or failed to fetch videos", style="red"
                )
                return {"success": False, "error": "No videos found"}

            # Save video list
            self.save_video_list(user_dir, user_info, videos)

            # Load processing status for resume
            status = self.load_processing_status(user_dir)

            # Process videos
            results = []

            # Statistics for this run
            attempted_this_run = 0
            successful_this_run = 0
            failed_this_run = 0
            skipped_this_run = 0

            # Count already completed videos from previous runs
            already_completed = len(status["completed"])

            with Progress() as progress:
                task = progress.add_task(
                    "[cyan]Processing videos...", total=len(videos)
                )

                for i, video in enumerate(videos):
                    bvid = video["bvid"]

                    # Skip if already processed
                    if bvid in status["completed"]:
                        console.print(
                            f"⏭️ Skipping already processed: {video['title']}",
                            style="dim",
                        )
                        skipped_this_run += 1
                        progress.update(task, advance=1)
                        continue

                    attempted_this_run += 1

                    try:
                        console.print(
                            f"\n🎬 Processing ({i+1}/{len(videos)}): {video['title']}",
                            style="cyan",
                        )

                        # Process video using existing handler with silent mode
                        video_url = video["video_url"]
                        result = self.bilibili_handler.process(
                            video_url,
                            output_dir=os.path.join(user_dir, "transcripts"),
                            cleanup=True,
                            silent=True,  # Use silent mode for batch processing
                            video_info=video,  # Pass video info for better file naming
                        )

                        result["video_info"] = video
                        results.append(result)

                        # Add to completed and remove from failed if it was there
                        if bvid not in status["completed"]:
                            status["completed"].append(bvid)
                        if bvid in status["failed"]:
                            status["failed"].remove(bvid)

                        successful_this_run += 1

                        console.print(
                            f"✅ Completed: {video['title']}", style="green"
                        )

                    except Exception as e:
                        console.print(
                            f"❌ Failed to process {video['title']}: {e}",
                            style="red",
                        )

                        # Add to failed only if not already completed
                        if (
                            bvid not in status["completed"]
                            and bvid not in status["failed"]
                        ):
                            status["failed"].append(bvid)

                        failed_this_run += 1

                        results.append(
                            {
                                "success": False,
                                "error": str(e),
                                "video_info": video,
                            }
                        )

                    # Save status after each video
                    self.save_processing_status(user_dir, status)
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
                user_info, videos, results, user_dir, run_stats
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
            console.print(
                f"📈 Overall: {len(status['completed'])} completed, "
                f"{len(status['failed'])} failed",
                style="dim",
            )

            return summary

        except Exception as e:
            console.print(f"❌ User processing failed: {e}", style="red")
            return {"success": False, "error": str(e)}

    def generate_summary(
        self,
        user_info: Dict[str, Any],
        videos: List[Dict[str, Any]],
        results: List[Dict[str, Any]],
        user_dir: str,
        run_stats: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate processing summary report.

        Args:
            user_info: User information
            videos: List of all videos
            results: Processing results from this run only
            user_dir: User directory path
            run_stats: Statistics from this processing run

        Returns:
            Summary dictionary
        """
        successful_results = [r for r in results if r.get("success", False)]
        failed_results = [r for r in results if not r.get("success", False)]

        # Calculate success rate for this run (only if videos were attempted)
        run_success_rate = 0.0
        if run_stats["attempted_this_run"] > 0:
            run_success_rate = (
                run_stats["successful_this_run"]
                / run_stats["attempted_this_run"]
            )

        # Calculate overall completion rate
        overall_completion_rate = 0.0
        if len(videos) > 0:
            overall_completion_rate = run_stats["total_completed"] / len(
                videos
            )

        summary = {
            "success": True,
            "user_info": user_info,
            "processing_stats": {
                "total_videos": len(videos),
                "processed_videos": len(
                    successful_results
                ),  # Videos processed in this run
                "failed_videos": len(
                    failed_results
                ),  # Videos failed in this run
                "skipped_videos": run_stats[
                    "skipped_this_run"
                ],  # Videos skipped in this run
                "run_success_rate": run_success_rate,  # Success rate for attempted
                "overall_completed": run_stats[
                    "total_completed"
                ],  # Total videos completed (including previous)
                "overall_failed": run_stats[
                    "total_failed"
                ],  # Total videos failed (including previous)
                "overall_completion_rate": overall_completion_rate,  # Overall %
                # Legacy field for backward compatibility (based on this run)
                "success_rate": run_success_rate,
                "generated_at": datetime.now().isoformat(),
            },
            "results": results,
        }

        # Save summary to file
        summary_file = os.path.join(user_dir, "user_summary.json")
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        console.print(f"📊 Summary saved to: {summary_file}", style="dim")

        return summary
