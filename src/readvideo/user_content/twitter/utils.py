"""Utility functions for Twitter content processing."""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from rich.console import Console

console = Console()


def parse_twitter_date(date_str: str) -> Optional[datetime]:
    """Parse Twitter pubDate string to datetime object.

    Args:
        date_str: Twitter pubDate string (RFC 2822 format)

    Returns:
        Datetime object or None if parsing fails
    """
    if not date_str:
        return None

    try:
        # Twitter RSS feeds use RFC 2822 format: "Mon, 01 Jan 2024 12:00:00 GMT"
        return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %Z")
    except ValueError:
        try:
            # Alternative format without timezone
            return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S")
        except ValueError:
            console.print(
                f"⚠️ Failed to parse date: {date_str}", style="yellow"
            )
            return None


def filter_tweets_by_date(
    tweets: List[Dict],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[Dict]:
    """Filter tweets by date range.

    Args:
        tweets: List of tweet dictionaries
        start_date: Start date filter (YYYY-MM-DD format)
        end_date: End date filter (YYYY-MM-DD format)

    Returns:
        Filtered list of tweets
    """
    if not start_date and not end_date:
        return tweets

    # Parse filter dates
    start_dt = None
    end_dt = None

    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            console.print(
                f"⚠️ Invalid start date format: {start_date}", style="yellow"
            )
            return tweets

    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            # Set end time to end of day
            end_dt = end_dt.replace(hour=23, minute=59, second=59)
        except ValueError:
            console.print(
                f"⚠️ Invalid end date format: {end_date}", style="yellow"
            )
            return tweets

    filtered_tweets = []

    for tweet in tweets:
        tweet_date = parse_twitter_date(tweet.get("pubDate", ""))
        if not tweet_date:
            continue

        # Apply date filters
        if start_dt and tweet_date < start_dt:
            continue
        if end_dt and tweet_date > end_dt:
            continue

        filtered_tweets.append(tweet)

    if start_date or end_date:
        console.print(
            f"📅 Date filter applied: {len(filtered_tweets)}/{len(tweets)} tweets",
            style="dim",
        )

    return filtered_tweets


def extract_tweet_info(nitter_url: str) -> tuple[Optional[str], Optional[str]]:
    """Extract tweet ID and username from Nitter URL.

    Args:
        nitter_url: Nitter URL

    Returns:
        Tuple of (username, tweet_id) or (None, None) if not found
    """
    match = re.search(r"/(\w+)/status/(\d+)", nitter_url)
    if match:
        return match.group(1), match.group(2)
    return None, None


def extract_tweet_id(nitter_url: str) -> Optional[str]:
    """Extract tweet ID from Nitter URL.

    Args:
        nitter_url: Nitter URL

    Returns:
        Tweet ID or None if not found
    """
    _, tweet_id = extract_tweet_info(nitter_url)
    return tweet_id


def generate_twitter_url(tweet_id: str, username: str) -> Optional[str]:
    """Generate official Twitter URL.

    Args:
        tweet_id: Tweet ID
        username: Twitter username

    Returns:
        Twitter URL or None if tweet_id is invalid
    """
    if tweet_id and username:
        return f"https://twitter.com/{username}/status/{tweet_id}"
    return None


def is_retweet(tweet: dict, target_username: str) -> bool:
    """Check if tweet is a retweet.

    Args:
        tweet: Tweet dictionary
        target_username: The username we're analyzing (without @)

    Returns:
        True if it's a retweet, False otherwise
    """
    creator = tweet.get("creator", "").lstrip("@")
    return creator != target_username


def is_reply(tweet: dict) -> bool:
    """Check if tweet is a reply.

    Args:
        tweet: Tweet dictionary

    Returns:
        True if it's a reply, False otherwise
    """
    title = tweet.get("title", "")
    return title.startswith("R to @")


def filter_tweets_by_content_type(
    tweets: List[Dict],
    target_username: str,
    include_retweets: bool = False,
    include_replies: bool = False,
) -> List[Dict]:
    """Filter tweets by content type.

    Args:
        tweets: List of tweet dictionaries
        target_username: The username we're analyzing (without @)
        include_retweets: Whether to include retweets
        include_replies: Whether to include replies

    Returns:
        Filtered list of tweets
    """
    filtered_tweets = []

    for tweet in tweets:
        # Add metadata fields
        tweet["is_retweet"] = is_retweet(tweet, target_username)
        tweet["is_reply"] = is_reply(tweet)
        tweet["tweet_type"] = "original"

        if tweet["is_retweet"]:
            tweet["tweet_type"] = "retweet"
            tweet["original_creator"] = tweet.get("creator", "").lstrip("@")
            if not include_retweets:
                continue
        elif tweet["is_reply"]:
            tweet["tweet_type"] = "reply"
            if not include_replies:
                continue

        filtered_tweets.append(tweet)

    return filtered_tweets


def clean_title_content(title: str) -> str:
    """Clean tweet title content.

    Args:
        title: Raw title text

    Returns:
        Cleaned title text
    """
    if not title:
        return ""

    # Clean HTML entities
    cleaned = (
        title.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    )

    # Remove "R to @username:" prefix (reply indicator)
    cleaned = re.sub(r"^R to @\\w+:\\s*", "", cleaned)

    return cleaned.strip()


def replace_localhost_links(text: str) -> str:
    """Replace localhost Nitter links with official Twitter links.

    Args:
        text: Text containing localhost links

    Returns:
        Text with replaced links
    """

    def replace_match(match):
        nitter_url = match.group(0)
        tweet_match = re.search(r"/(\w+)/status/(\d+)", nitter_url)
        if tweet_match:
            username_in_link = tweet_match.group(1)
            tweet_id_in_link = tweet_match.group(2)
            return f"https://twitter.com/{username_in_link}/status/{tweet_id_in_link}"
        return nitter_url

    return re.sub(r"localhost:42853/\w+/status/\d+(?:#m)?", replace_match, text)


def clean_tweet_content(content: str) -> str:
    """Clean tweet content for display.

    Args:
        content: Raw tweet content

    Returns:
        Cleaned content
    """
    if not content:
        return ""

    # Remove HTML tags but preserve line breaks
    cleaned = re.sub(r"<[^>]+>", "", content).strip()

    # Clean HTML entities
    cleaned = (
        cleaned.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    )

    # Replace localhost links with Twitter links
    cleaned = replace_localhost_links(cleaned)

    # Remove reply prefix
    cleaned = re.sub(r"^R to @\\w+:\\s*", "", cleaned)

    return cleaned


def save_tweets_to_json(
    tweets: List[Dict], username: str, output_dir: Path
) -> Optional[Path]:
    """Save tweets to JSON file.

    Args:
        tweets: List of tweet dictionaries
        username: Twitter username
        output_dir: Output directory

    Returns:
        Path to saved file or None if failed
    """
    filename = output_dir / f"{username}_tweets.json"

    # Add metadata
    data = {
        "metadata": {
            "username": username,
            "fetch_time": datetime.now().isoformat(),
            "total_tweets": len(tweets),
            "source": "Nitter RSS API",
        },
        "tweets": tweets,
    }

    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        console.print(f"💾 JSON saved: {filename}", style="green")
        return filename
    except Exception as e:
        console.print(f"❌ JSON save failed: {e}", style="red")
        return None


def save_tweets_to_markdown(
    tweets: List[Dict], username: str, output_dir: Path
) -> Optional[Path]:
    """Save tweets to Markdown file.

    Args:
        tweets: List of tweet dictionaries
        username: Twitter username
        output_dir: Output directory

    Returns:
        Path to saved file or None if failed
    """
    filename = output_dir / f"{username}_tweets.md"

    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"# 📱 @{username} Tweet Collection\n\n")
            f.write(
                f"**Fetch Time**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            )
            f.write(f"**Total Tweets**: {len(tweets)}\n")
            f.write("**Data Source**: Nitter RSS API\n\n")
            f.write("---\n\n")

            for i, tweet in enumerate(tweets, 1):
                # Extract tweet info
                original_username, tweet_id = extract_tweet_info(tweet["link"])

                f.write(f"## 推文 #{i}\n\n")
                f.write(f"**发布时间**: {tweet['pubDate']}\n")

                # Check tweet type from metadata
                # (added by filter_tweets_by_content_type)
                tweet_type = tweet.get("tweet_type", "original")

                if tweet_type == "retweet":
                    # This is a retweet - show original author info
                    original_creator = tweet.get(
                        "original_creator",
                        tweet.get("creator", "").lstrip("@"),
                    )
                    f.write(f"**类型**: 转推 @{original_creator} 的内容\n")
                    if tweet_id and original_username:
                        twitter_url = generate_twitter_url(
                            tweet_id, original_username
                        )
                        f.write(f"**原推链接**: {twitter_url}\n")
                elif tweet_type == "reply":
                    # This is a reply
                    f.write("**类型**: 回复\n")
                    if tweet_id and original_username:
                        twitter_url = generate_twitter_url(
                            tweet_id, original_username
                        )
                        f.write(f"**Twitter链接**: {twitter_url}\n")
                else:
                    # This is an original tweet
                    if tweet_id and original_username:
                        twitter_url = generate_twitter_url(
                            tweet_id, original_username
                        )
                        f.write(f"**Twitter链接**: {twitter_url}\n")

                f.write("\n")

                # Use description as main content source (preserves formatting)
                if tweet["description"]:
                    desc_text = tweet["description"]

                    # Clean HTML tags but preserve line breaks
                    desc_clean = re.sub(r"<[^>]+>", "", desc_text).strip()
                    # Clean HTML entities
                    desc_clean = (
                        desc_clean.replace("&lt;", "<")
                        .replace("&gt;", ">")
                        .replace("&amp;", "&")
                    )
                    # Replace localhost links
                    desc_clean = replace_localhost_links(desc_clean)
                    # Remove reply prefix
                    desc_clean = re.sub(r"^R to @\w+:\s*", "", desc_clean)

                    # Write tweet content (preserve line format)
                    f.write(f"{desc_clean}\n\n")
                else:
                    # Fall back to title if no description
                    clean_content = clean_title_content(tweet["title"])
                    f.write(f"{clean_content}\n\n")

                f.write("---\n\n")

        console.print(f"📄 Markdown saved: {filename}", style="green")
        return filename

    except Exception as e:
        console.print(f"❌ Markdown save failed: {e}", style="red")
        return None
