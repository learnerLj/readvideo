"""RSS fetcher with pagination support for Twitter content."""

import asyncio
import logging
import re
from typing import Callable, Dict, List, Optional

import defusedxml.ElementTree as ET
import httpx
from rich.console import Console

console = Console()
logger = logging.getLogger(__name__)


class RSSFetcher:
    """RSS API client with pagination support."""

    def __init__(self, nitter_url: str = "http://10.144.0.3:8080"):
        """Initialize RSS fetcher.

        Args:
            nitter_url: Base URL of the Nitter instance
        """
        self.nitter_url = nitter_url.rstrip("/")
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0),
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/91.0.4472.124 Safari/537.36"
                ),
                "Accept": "application/rss+xml, application/xml, text/xml",
                "Accept-Language": "en-US,en;q=0.9",
                "Connection": "keep-alive",
            },
        )

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()

    async def get_cursor_from_html(self, username: str) -> Optional[str]:
        """Get first cursor from HTML page for pagination.

        Args:
            username: Twitter username

        Returns:
            Cursor string or None if not found
        """
        url = f"{self.nitter_url}/{username}"
        try:
            response = await self.client.get(url)
            response.raise_for_status()

            cursor_match = re.search(r'href="\?cursor=([^"]*)"', response.text)
            cursor = cursor_match.group(1) if cursor_match else None
            logger.debug(
                f"Found cursor from HTML: {cursor[:50] if cursor else None}..."
            )
            return cursor

        except Exception as e:
            logger.error(f"Failed to get cursor: {e}")
            return None

    async def fetch_rss_page(
        self,
        username: str,
        cursor: Optional[str] = None,
        exclude_retweets: bool = True,
        exclude_replies: bool = True,
    ) -> tuple[List[Dict], bool]:
        """Fetch single RSS page.

        Args:
            username: Twitter username
            cursor: Pagination cursor
            exclude_retweets: Whether to exclude retweets
            exclude_replies: Whether to exclude replies

        Returns:
            Tuple of (tweets_list, success_flag)
        """
        # Build URL
        url = f"{self.nitter_url}/{username}/rss"

        params = []
        if cursor:
            params.append(f"cursor={cursor}")
        if exclude_retweets:
            params.append("e-retweets=on")
        if exclude_replies:
            params.append("e-replies=on")

        if params:
            url += "?" + "&".join(params)

        logger.info(f"📡 Fetching: {url[:80]}{'...' if len(url) > 80 else ''}")

        try:
            response = await self.client.get(url)

            # Detailed status code checking
            logger.debug(f"🔍 HTTP status: {response.status_code}")
            logger.debug(
                f"🔍 Content-Type: {response.headers.get('content-type', 'unknown')}"
            )
            logger.debug(f"🔍 Content length: {len(response.content)} bytes")

            if response.status_code == 429:
                logger.warning(f"⚠️  Rate limited (429): {response.text[:200]}...")
                return [], False
            elif response.status_code == 503:
                logger.warning(
                    f"⚠️  Service unavailable (503): {response.text[:200]}..."
                )
                return [], False

            response.raise_for_status()

            # Check if response content is empty
            if not response.content or len(response.content) < 50:
                logger.warning(f"⚠️  Response too short: {len(response.content)} bytes")
                logger.debug(f"📝 Content: {response.text[:200]}...")
                return [], False

            # Parse RSS XML
            try:
                root = ET.fromstring(response.content)
            except ET.ParseError as parse_error:
                logger.error(f"❌ XML parse error: {parse_error}")
                logger.debug(f"📝 First 500 chars: {response.text[:500]}...")
                return [], False

            # Extract tweets
            tweets = []
            items = root.findall(".//item")
            logger.debug(f"🔍 Found {len(items)} XML items")

            for i, item in enumerate(items):
                # Safely extract text content with None checking
                def safe_text(element):
                    return (
                        element.text
                        if element is not None and element.text is not None
                        else ""
                    )

                tweet = {
                    "title": safe_text(item.find("title")),
                    "description": safe_text(item.find("description")),
                    "link": safe_text(item.find("link")),
                    "pubDate": safe_text(item.find("pubDate")),
                    "guid": safe_text(item.find("guid")),
                    "creator": safe_text(
                        item.find(".//{http://purl.org/dc/elements/1.1/}creator")
                    ),
                }
                tweets.append(tweet)

                # Log first 3 tweets for debugging
                if i < 3:
                    logger.debug(f"  📝 Tweet {i+1}: {tweet['title'][:50]}...")

            logger.info(f"✅ Parsed {len(tweets)} tweets")
            return tweets, True

        except httpx.TimeoutException as e:
            logger.error(f"❌ Request timeout: {e}")
            return [], False
        except httpx.ConnectError as e:
            logger.error(f"❌ Connection error: {e}")
            return [], False
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ HTTP error: {e}")
            logger.debug(f"📝 Response status: {e.response.status_code}")
            logger.debug(f"📝 Response content: {e.response.text[:200]}...")
            return [], False
        except Exception as e:
            logger.error(f"❌ Unknown error: {type(e).__name__}: {e}")
            return [], False

    async def get_all_tweets(
        self,
        username: str,
        max_pages: int = 50,
        exclude_retweets: bool = True,
        exclude_replies: bool = True,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> List[Dict]:
        """Get all tweets using RSS API with pagination.

        Args:
            username: Twitter username
            max_pages: Maximum pages to fetch
            exclude_retweets: Whether to exclude retweets
            exclude_replies: Whether to exclude replies
            progress_callback: Optional callback for progress updates

        Returns:
            List of tweet dictionaries
        """

        def update_progress(msg: str):
            if progress_callback:
                progress_callback(msg)
            logger.info(msg)

        update_progress(f"🐦 Fetching @{username} tweets via RSS")

        all_tweets = []
        seen_tweet_ids = set()
        page_num = 1

        # Get first page (no cursor)
        update_progress(f"📄 Page {page_num} (first page)")
        tweets, success = await self.fetch_rss_page(
            username, None, exclude_retweets, exclude_replies
        )

        if not success or not tweets:
            logger.error("❌ Failed to get first page")
            return []

        # Add first page tweet IDs to seen set
        for tweet in tweets:
            tweet_id = self._extract_tweet_id(tweet["link"])
            if tweet_id:
                seen_tweet_ids.add(tweet_id)

        all_tweets.extend(tweets)
        update_progress(f"📊 Total tweets: {len(all_tweets)}")

        # Get first cursor for pagination
        cursor = await self.get_cursor_from_html(username)
        if not cursor:
            logger.warning("❌ No pagination cursor found, returning first page only")
            return all_tweets

        logger.info(f"🔑 Found pagination cursor: {cursor[:50]}...")

        # Paginate through remaining pages
        page_num += 1

        while page_num <= max_pages and cursor:
            update_progress(f"📄 Page {page_num}")

            # Add delay to avoid rate limiting
            if page_num > 2:
                wait_time = 2
                logger.debug(f"⏳ Waiting {wait_time}s to avoid rate limiting...")
                await asyncio.sleep(wait_time)

            tweets, success = await self.fetch_rss_page(
                username, cursor, exclude_retweets, exclude_replies
            )

            if not success:
                logger.warning(f"❌ Page {page_num} failed")
                logger.info("⚠️  Waiting 5s before retry...")
                await asyncio.sleep(5)

                # Retry once
                tweets, success = await self.fetch_rss_page(
                    username, cursor, exclude_retweets, exclude_replies
                )
                if not success:
                    logger.error("❌ Retry failed, stopping")
                    break
                else:
                    logger.info("✅ Retry successful")

            if not tweets:
                logger.info(
                    f"✅ Page {page_num} returned 0 tweets - reached end of timeline"
                )
                break

            # Detect duplicate tweets
            new_tweets = []
            duplicate_count = 0

            for tweet in tweets:
                tweet_id = self._extract_tweet_id(tweet["link"])
                if tweet_id and tweet_id not in seen_tweet_ids:
                    seen_tweet_ids.add(tweet_id)
                    new_tweets.append(tweet)
                else:
                    duplicate_count += 1

            if duplicate_count > 0:
                logger.info(f"⚠️  Found {duplicate_count} duplicate tweets, skipping")

            if len(new_tweets) == 0:
                logger.info(f"✅ Page {page_num} all duplicates, fetching complete")
                break

            all_tweets.extend(new_tweets)
            update_progress(
                f"📊 Total tweets: {len(all_tweets)} (+{len(new_tweets)} new)"
            )

            # Get next page cursor
            try:
                html_url = f"{self.nitter_url}/{username}?cursor={cursor}"
                response = await self.client.get(html_url)
                response.raise_for_status()

                if not response.text:
                    logger.info("✅ Empty response for cursor page, fetching complete")
                    break

                cursor_match = re.search(r'href="\?cursor=([^"]*)"', response.text)

                if cursor_match:
                    new_cursor = cursor_match.group(1)
                    if new_cursor != cursor:  # Ensure cursor changed
                        cursor = new_cursor
                        logger.debug(f"🔑 Next cursor: {cursor[:50]}...")
                    else:
                        logger.info("✅ Cursor unchanged, reached last page")
                        break
                else:
                    logger.info("✅ No more cursors found, fetching complete")
                    break

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    logger.info(
                        "✅ Cursor page not found (404), reached end of timeline"
                    )
                else:
                    logger.warning(
                        f"⚠️  HTTP error getting cursor: " f"{e.response.status_code}"
                    )
                break
            except Exception as e:
                error_type = type(e).__name__
                logger.warning(f"⚠️  Failed to get next cursor: {error_type}: {e}")
                logger.info("✅ Stopping pagination due to cursor error")
                break

            page_num += 1

        update_progress("🎉 Fetching complete")
        logger.info(f"- **Total pages**: {page_num - 1}")
        logger.info(f"- **Total tweets**: {len(all_tweets)}")

        return all_tweets

    def _extract_tweet_id(self, nitter_url: str) -> Optional[str]:
        """Extract tweet ID from Nitter URL.

        Args:
            nitter_url: Nitter URL

        Returns:
            Tweet ID or None if not found
        """
        # Import here to avoid circular imports
        from .utils import extract_tweet_id

        return extract_tweet_id(nitter_url)
