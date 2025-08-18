"""Bilibili user content processing handler."""

import os
import re
import json
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, TaskID

try:
    import bilibili_api
    BILIBILI_API_AVAILABLE = True
except ImportError:
    BILIBILI_API_AVAILABLE = False

from ..platforms.bilibili import BilibiliHandler

console = Console()


class BilibiliUserHandler:
    """Handler for processing all videos from a Bilibili user."""
    
    def __init__(self, whisper_model_path: str = "~/.whisper-models/ggml-large-v3.bin"):
        """Initialize user handler.
        
        Args:
            whisper_model_path: Path to whisper model for transcription
        """
        self.whisper_model_path = whisper_model_path
        self.bilibili_handler = BilibiliHandler(whisper_model_path)
    
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
            r'space\.bilibili\.com/(\d+)',
            r'bilibili\.com/(\d+)',
            r'/(\d+)/?$'
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
        if not BILIBILI_API_AVAILABLE:
            return {
                "uid": uid,
                "name": f"User_{uid}",
                "follower": 0,
                "following": 0,
                "error": "bilibili-api not available"
            }
        
        try:
            user = bilibili_api.user.User(uid)
            user_info = await user.get_relation_info()
            
            return {
                "uid": uid,
                "name": user_info.get("name", f"User_{uid}"),
                "follower": user_info.get("follower", 0),
                "following": user_info.get("following", 0)
            }
        except Exception as e:
            console.print(f"❌ Failed to get user info for UID {uid}: {e}", style="red")
            return {
                "uid": uid,
                "name": f"User_{uid}",
                "follower": 0,
                "following": 0
            }
    
    async def get_user_videos(self, uid: int, start_date: Optional[str] = None, 
                             max_videos: Optional[int] = None) -> List[Dict[str, Any]]:
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
            
            console.print(f"🔍 Fetching videos for user {uid}...", style="cyan")
            
            # Parse start date if provided
            start_timestamp = None
            if start_date:
                try:
                    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                    start_timestamp = int(start_dt.timestamp())
                except ValueError:
                    console.print(f"⚠️ Invalid date format: {start_date}, ignoring date filter", style="yellow")
            
            # Fetch all videos with pagination
            while True:
                try:
                    video_data = await user.get_videos(pn=page, ps=30)
                    videos = video_data.get('list', {}).get('vlist', [])
                    
                    if not videos:
                        break
                    
                    # Filter by date if specified
                    for video in videos:
                        if start_timestamp and video.get('created', 0) < start_timestamp:
                            continue
                        
                        # Add formatted date and URL
                        video['created_date'] = datetime.fromtimestamp(
                            video.get('created', 0)
                        ).strftime("%Y-%m-%d")
                        video['video_url'] = f"https://www.bilibili.com/video/{video['bvid']}"
                        
                        all_videos.append(video)
                    
                    console.print(f"📄 Fetched page {page}, total videos: {len(all_videos)}", style="dim")
                    page += 1
                    
                    # Stop if we've reached the date limit or max videos
                    if start_timestamp and videos and videos[-1].get('created', 0) < start_timestamp:
                        break
                    if max_videos and len(all_videos) >= max_videos:
                        break
                        
                except Exception as e:
                    console.print(f"⚠️ Error fetching page {page}: {e}", style="yellow")
                    break
            
            # Apply max_videos limit
            if max_videos and len(all_videos) > max_videos:
                all_videos = all_videos[:max_videos]
            
            console.print(f"✅ Found {len(all_videos)} videos to process", style="green")
            return all_videos
            
        except Exception as e:
            console.print(f"❌ Failed to get videos for user {uid}: {e}", style="red")
            return []
    
    def create_user_directory(self, output_dir: str, user_info: Dict[str, Any]) -> str:
        """Create user-specific output directory.
        
        Args:
            output_dir: Base output directory
            user_info: User information dictionary
            
        Returns:
            Path to created user directory
        """
        safe_name = re.sub(r'[^\w\-_.]', '_', user_info['name'])
        user_dir = os.path.join(output_dir, f"{safe_name}_{user_info['uid']}")
        
        # Create directory structure
        os.makedirs(user_dir, exist_ok=True)
        os.makedirs(os.path.join(user_dir, "transcripts"), exist_ok=True)
        
        return user_dir
    
    def save_video_list(self, user_dir: str, user_info: Dict[str, Any], videos: List[Dict[str, Any]]):
        """Save video list to JSON file.
        
        Args:
            user_dir: User directory path
            user_info: User information
            videos: List of video information
        """
        video_list_file = os.path.join(user_dir, "video_list.json")
        
        data = {
            "user_info": {
                **user_info,
                "total_videos": len(videos)
            },
            "videos": videos,
            "generated_at": datetime.now().isoformat()
        }
        
        with open(video_list_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        console.print(f"💾 Saved video list to: {video_list_file}", style="dim")
    
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
            with open(status_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            console.print(f"⚠️ Error loading processing status: {e}", style="yellow")
            return {"completed": [], "failed": [], "skipped": []}
    
    def save_processing_status(self, user_dir: str, status: Dict[str, List[str]]):
        """Save processing status.
        
        Args:
            user_dir: User directory path
            status: Status dictionary
        """
        status_file = os.path.join(user_dir, "processing_status.json")
        
        status["last_update"] = datetime.now().isoformat()
        
        with open(status_file, 'w', encoding='utf-8') as f:
            json.dump(status, f, ensure_ascii=False, indent=2)
    
    def process_user(self, user_input: str, output_dir: str,
                    start_date: Optional[str] = None, 
                    max_videos: Optional[int] = None) -> Dict[str, Any]:
        """Process all videos from a user.
        
        Args:
            user_input: User UID or space URL
            output_dir: Output directory (required)
            start_date: Start date filter (YYYY-MM-DD)
            max_videos: Maximum number of videos to process
            
        Returns:
            Processing results summary
        """
        return asyncio.run(self._process_user_async(user_input, output_dir, start_date, max_videos))
    
    async def _process_user_async(self, user_input: str, output_dir: str,
                                 start_date: Optional[str] = None,
                                 max_videos: Optional[int] = None) -> Dict[str, Any]:
        """Async implementation of user processing."""
        
        try:
            # Extract UID
            uid = self.extract_uid(user_input)
            console.print(f"🎯 Processing user: {uid}", style="bold cyan")
            
            # Get user info
            user_info = await self.get_user_info(uid)
            console.print(f"👤 User: {user_info['name']} (Followers: {user_info['follower']})", style="cyan")
            
            # Create user directory
            user_dir = self.create_user_directory(output_dir, user_info)
            console.print(f"📁 Output directory: {user_dir}", style="cyan")
            
            # Get videos
            videos = await self.get_user_videos(uid, start_date, max_videos)
            if not videos:
                console.print("❌ No videos found or failed to fetch videos", style="red")
                return {"success": False, "error": "No videos found"}
            
            # Save video list
            self.save_video_list(user_dir, user_info, videos)
            
            # Load processing status for resume
            status = self.load_processing_status(user_dir)
            
            # Process videos
            results = []
            failed_count = 0
            
            with Progress() as progress:
                task = progress.add_task("[cyan]Processing videos...", total=len(videos))
                
                for i, video in enumerate(videos):
                    bvid = video['bvid']
                    
                    # Skip if already processed
                    if bvid in status['completed']:
                        console.print(f"⏭️ Skipping already processed: {video['title']}", style="dim")
                        status['skipped'].append(bvid)
                        progress.update(task, advance=1)
                        continue
                    
                    try:
                        console.print(f"\n🎬 Processing ({i+1}/{len(videos)}): {video['title']}", style="cyan")
                        
                        # Process video using existing handler with silent mode
                        video_url = video['video_url']
                        result = self.bilibili_handler.process(
                            video_url,
                            output_dir=os.path.join(user_dir, "transcripts"),
                            cleanup=True,
                            silent=True  # Use silent mode for batch processing
                        )
                        
                        result['video_info'] = video
                        results.append(result)
                        status['completed'].append(bvid)
                        
                        console.print(f"✅ Completed: {video['title']}", style="green")
                        
                    except Exception as e:
                        console.print(f"❌ Failed to process {video['title']}: {e}", style="red")
                        status['failed'].append(bvid)
                        failed_count += 1
                        
                        results.append({
                            "success": False,
                            "error": str(e),
                            "video_info": video
                        })
                    
                    # Save status after each video
                    self.save_processing_status(user_dir, status)
                    progress.update(task, advance=1)
            
            # Generate final summary
            summary = self.generate_summary(user_info, videos, results, user_dir)
            
            console.print(f"\n🎉 Processing completed!", style="bold green")
            console.print(f"✅ Successful: {len(status['completed'])}", style="green")
            console.print(f"❌ Failed: {len(status['failed'])}", style="red")
            console.print(f"⏭️ Skipped: {len(status['skipped'])}", style="yellow")
            
            return summary
            
        except Exception as e:
            console.print(f"❌ User processing failed: {e}", style="red")
            return {"success": False, "error": str(e)}
    
    def generate_summary(self, user_info: Dict[str, Any], videos: List[Dict[str, Any]], 
                        results: List[Dict[str, Any]], user_dir: str) -> Dict[str, Any]:
        """Generate processing summary report.
        
        Args:
            user_info: User information
            videos: List of all videos
            results: Processing results
            user_dir: User directory path
            
        Returns:
            Summary dictionary
        """
        successful_results = [r for r in results if r.get('success', False)]
        failed_results = [r for r in results if not r.get('success', False)]
        
        summary = {
            "success": True,
            "user_info": user_info,
            "processing_stats": {
                "total_videos": len(videos),
                "processed_videos": len(successful_results),
                "failed_videos": len(failed_results),
                "success_rate": len(successful_results) / len(videos) if videos else 0,
                "generated_at": datetime.now().isoformat()
            },
            "results": results
        }
        
        # Save summary to file
        summary_file = os.path.join(user_dir, "user_summary.json")
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        console.print(f"📊 Summary saved to: {summary_file}", style="dim")
        
        return summary