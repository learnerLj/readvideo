"""Main Twitter content handler for readvideo."""

from pathlib import Path
from typing import Dict, Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .rss_fetcher import RSSFetcher
from .utils import (
    filter_tweets_by_content_type,
    filter_tweets_by_date,
    save_tweets_to_json,
    save_tweets_to_markdown,
)

console = Console()


class TwitterHandler:
    """Handler for fetching Twitter content via RSS."""

    def __init__(self, nitter_url: str = "http://10.144.0.3:8080"):
        """Initialize TwitterHandler.

        Args:
            nitter_url: Base URL of the Nitter instance
        """
        self.nitter_url = nitter_url.rstrip("/")
        self.fetcher = RSSFetcher(self.nitter_url)

    async def process_user(
        self,
        username: str,
        output_dir: str,
        max_pages: int = 50,
        exclude_retweets: bool = True,
        exclude_replies: bool = True,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict:
        """Process all tweets from a Twitter user.

        Args:
            username: Twitter username (without @)
            output_dir: Output directory for saved files
            max_pages: Maximum pages to fetch
            exclude_retweets: Whether to exclude retweets
            exclude_replies: Whether to exclude replies
            start_date: Start date filter (YYYY-MM-DD format)
            end_date: End date filter (YYYY-MM-DD format)

        Returns:
            Dict containing processing results
        """
        console.print(f"🐦 Processing Twitter user: @{username}", style="bold cyan")
        console.print(f"🌐 Using Nitter instance: {self.nitter_url}", style="dim")

        # Validate username
        if not self._validate_username(username):
            return {
                "success": False,
                "error": "Invalid username format",
                "username": username,
            }

        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Fetching tweets...", total=None)

                # Fetch all tweets
                tweets = await self.fetcher.get_all_tweets(
                    username=username,
                    max_pages=max_pages,
                    exclude_retweets=exclude_retweets,
                    exclude_replies=exclude_replies,
                    progress_callback=lambda msg: progress.update(
                        task, description=msg
                    ),
                )

                progress.update(task, description="Processing complete")

            if not tweets:
                return {
                    "success": False,
                    "error": "No tweets found or failed to fetch",
                    "username": username,
                    "total_tweets": 0,
                }

            # Apply date filtering if specified
            if start_date or end_date:
                console.print("📅 Applying date filter...", style="dim")
                original_count = len(tweets)
                tweets = filter_tweets_by_date(tweets, start_date, end_date)
                if len(tweets) < original_count:
                    console.print(
                        f"📅 Date filter: {len(tweets)}/{original_count} tweets "
                        "match criteria",
                        style="dim",
                    )

            # Apply content type filtering
            console.print("🔍 Applying content filter...", style="dim")
            pre_filter_count = len(tweets)
            tweets = filter_tweets_by_content_type(
                tweets,
                username,
                include_retweets=not exclude_retweets,
                include_replies=not exclude_replies,
            )

            if len(tweets) < pre_filter_count:
                retweets_filtered = sum(1 for t in tweets if t.get("is_retweet", False))
                replies_filtered = sum(1 for t in tweets if t.get("is_reply", False))
                original_tweets = len(tweets) - retweets_filtered - replies_filtered

                console.print(
                    f"🔍 Content filter: {len(tweets)} tweets kept "
                    f"({original_tweets} original, {retweets_filtered} retweets, "
                    f"{replies_filtered} replies)",
                    style="dim",
                )

            if not tweets:
                return {
                    "success": False,
                    "error": "No tweets found matching filter criteria",
                    "username": username,
                    "total_tweets": 0,
                }

            # Save results
            console.print(f"💾 Saving {len(tweets)} tweets...", style="bold green")

            json_file = save_tweets_to_json(tweets, username, output_path)
            markdown_file = save_tweets_to_markdown(tweets, username, output_path)

            return {
                "success": True,
                "username": username,
                "total_tweets": len(tweets),
                "output_files": {
                    "json": str(json_file) if json_file else None,
                    "markdown": str(markdown_file) if markdown_file else None,
                },
                "output_dir": str(output_path),
            }

        except Exception as e:
            console.print(f"❌ Error processing user @{username}: {e}", style="red")
            return {
                "success": False,
                "error": str(e),
                "username": username,
            }

    def _validate_username(self, username: str) -> bool:
        """Validate Twitter username format.

        Args:
            username: Username to validate

        Returns:
            True if valid, False otherwise
        """
        if not username:
            return False

        # Remove @ if present
        if username.startswith("@"):
            username = username[1:]

        # Basic validation: alphanumeric and underscore, 1-15 chars
        return (username.isalnum() or "_" in username) and 1 <= len(username) <= 15

    def get_user_info(self, username: str) -> Dict:
        """Get basic information about a Twitter user.

        Args:
            username: Twitter username

        Returns:
            Dict containing user information
        """
        return {
            "platform": "twitter",
            "username": username,
            "nitter_url": self.nitter_url,
        }
