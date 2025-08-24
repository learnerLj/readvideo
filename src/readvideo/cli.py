"""Command line interface for readvideo."""

import asyncio
import sys
from typing import Optional, Union

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .core.transcript_fetcher import is_youtube_url
from .platforms.bilibili import BilibiliHandler
from .platforms.local import LocalMediaHandler
from .platforms.youtube import YouTubeHandler
from .user_content.bilibili_user import BilibiliUserHandler
from .user_content.twitter import TwitterHandler
from .user_content.utils import validate_date_with_range_check
from .user_content.youtube_user import YouTubeUserHandler

console = Console()


def print_banner():
    """Print application banner."""
    banner = """
[bold cyan]ReadVideo[/bold cyan] - Video & Audio Transcription Tool

Supported Platforms:
  • [green]YouTube[/green] - Prioritize existing subtitles, fallback to transcription
  • [blue]Bilibili[/blue] - Auto download and transcribe audio
  • [yellow]Local Files[/yellow] - Support audio and video file transcription
    """
    console.print(Panel(banner, title="🎬 ReadVideo", border_style="cyan"))


def detect_input_type(input_str: str) -> str:
    """Detect the type of input (youtube, bilibili, or local file).

    Args:
        input_str: Input string (URL or file path)

    Returns:
        Input type: 'youtube', 'bilibili', or 'local'
    """
    if is_youtube_url(input_str):
        return "youtube"
    elif "bilibili.com" in input_str or "b23.tv" in input_str:
        return "bilibili"
    else:
        return "local"


@click.command()
@click.argument("input_source", required=True)
@click.option(
    "--auto-detect",
    is_flag=True,
    help="Enable automatic language detection (default: Chinese)",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    help="Output directory (default: current directory or input file directory)",
)
@click.option(
    "--no-cleanup", is_flag=True, help="Do not clean up temporary files"
)
@click.option(
    "--info-only",
    is_flag=True,
    help="Show input information only, do not process",
)
@click.option(
    "--whisper-model",
    default="~/.whisper-models/ggml-large-v3.bin",
    help="Path to Whisper model file",
)
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option(
    "--proxy", help="HTTP proxy address (e.g., http://127.0.0.1:8080)"
)
def main(
    input_source: str,
    auto_detect: bool,
    output_dir: Optional[str],
    no_cleanup: bool,
    info_only: bool,
    whisper_model: str,
    verbose: bool,
    proxy: Optional[str],
):
    """ReadVideo - Video and Audio Transcription Tool

    INPUT_SOURCE: Video URL or local media file path

    Examples:
      readvideo https://www.youtube.com/watch?v=abc123
      readvideo https://www.bilibili.com/video/BV1234567890
      readvideo ~/Music/podcast.mp3
      readvideo ~/Videos/lecture.mp4
    """
    if not verbose:
        print_banner()

    # Detect input type
    input_type = detect_input_type(input_source)

    if verbose:
        console.print(f"🔍 Detected input type: {input_type}", style="dim")

    try:
        # Initialize appropriate handler
        handler: Union[YouTubeHandler, BilibiliHandler, LocalMediaHandler]
        if input_type == "youtube":
            handler = YouTubeHandler(whisper_model, proxy=proxy)
            if not handler.validate_url(input_source):
                console.print("❌ Invalid YouTube URL", style="red")
                sys.exit(1)
        elif input_type == "bilibili":
            handler = BilibiliHandler(whisper_model)
            if not handler.validate_url(input_source):
                console.print("❌ Invalid Bilibili URL", style="red")
                sys.exit(1)
        else:  # local file
            handler = LocalMediaHandler(whisper_model)
            if not handler.validate_file(input_source):
                console.print(
                    f"❌ File not found or format not supported: {input_source}",
                    style="red",
                )
                show_supported_formats(handler)
                sys.exit(1)

        # Show info only if requested
        if info_only:
            show_info(handler, input_source, input_type)
            return

        # Process the input
        result = handler.process(
            input_source,
            auto_detect=auto_detect,
            output_dir=output_dir,
            cleanup=not no_cleanup,
        )

        # Display results
        show_results(result, verbose)

    except KeyboardInterrupt:
        console.print("\n⚠️ Operation interrupted by user", style="yellow")
        sys.exit(1)
    except Exception as e:
        console.print(f"❌ Processing failed: {e}", style="red")
        if verbose:
            import traceback

            console.print(traceback.format_exc(), style="dim")
        sys.exit(1)


def show_info(handler, input_source: str, input_type: str):
    """Show information about the input without processing."""

    try:
        if input_type in ["youtube", "bilibili"]:
            info = handler.get_video_info(input_source)

            table = Table(show_header=False, box=None)
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="white")

            table.add_row("Platform", info.get("platform", "").title())
            table.add_row("URL", info.get("url", ""))

            if input_type == "youtube":
                table.add_row("Video ID", info.get("video_id", ""))
                table.add_row(
                    "Has Transcripts",
                    "Yes" if info.get("has_transcripts") else "No",
                )

                transcripts = info.get("available_transcripts", {})
                if transcripts.get("manual"):
                    languages = [t["language"] for t in transcripts["manual"]]
                    table.add_row("Manual Subtitles", ", ".join(languages))
                if transcripts.get("generated"):
                    languages = [
                        t["language"] for t in transcripts["generated"]
                    ]
                    table.add_row("Auto Subtitles", ", ".join(languages))
            else:  # bilibili
                table.add_row("BV ID", info.get("bv_id", ""))
                table.add_row("Note", info.get("note", ""))

            console.print(table)

        else:  # local file
            info = handler.get_file_info(input_source)

            table = Table(show_header=False, box=None)
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="white")

            table.add_row("Filename", info["name"])
            table.add_row("Format", info["extension"].upper())
            table.add_row("Size", f"{info['size'] / 1024 / 1024:.1f} MB")
            table.add_row("Type", "Audio" if info["is_audio"] else "Video")

            if info.get("duration_formatted"):
                table.add_row("Duration", info["duration_formatted"])

            console.print(table)

    except Exception as e:
        console.print(f"❌ Failed to get information: {e}", style="red")


def show_results(result: dict, verbose: bool):
    """Show processing results."""
    if not result.get("success"):
        console.print("❌ Processing failed", style="red")
        return

    console.print("\n✅ Processing completed!", style="bold green")

    # Create results table
    table = Table(show_header=False, box=None)
    table.add_column("Item", style="cyan")
    table.add_column("Information", style="white")

    table.add_row("Platform", result.get("platform", "").title())
    table.add_row(
        "Method",
        (
            "Transcript"
            if result.get("method") == "transcript"
            else "Audio Transcription"
        ),
    )
    table.add_row("Output File", result.get("output_file", ""))

    if result.get("method") == "transcript":
        transcript_info = result.get("transcript_info", {})
        table.add_row("Subtitle Type", transcript_info.get("type", ""))
        table.add_row("Language", transcript_info.get("language", ""))
        if result.get("segment_count"):
            table.add_row("Segments", str(result["segment_count"]))
    else:
        table.add_row("Language", result.get("language", ""))

    console.print(table)

    # Show text preview
    text = result.get("text", "")
    if text:
        preview = text[:200] + "..." if len(text) > 200 else text
        console.print(f"\n📝 Transcription preview:\n{preview}", style="dim")

    if verbose and result.get("temp_files"):
        console.print(
            f"\n🗑️ Temporary files: {len(result['temp_files'])} cleaned up",
            style="dim",
        )


def show_supported_formats(handler):
    """Show supported file formats."""
    formats = handler.list_supported_formats()

    console.print("\n📋 Supported file formats:", style="bold")

    table = Table(show_header=False, box=None)
    table.add_column("Type", style="cyan")
    table.add_column("Formats", style="white")

    table.add_row("Audio", ", ".join(formats["audio_formats"]))
    table.add_row("Video", ", ".join(formats["video_formats"]))

    console.print(table)


@click.command()
def info():
    """Show tool information and usage help."""
    print_banner()

    console.print("\n🚀 Usage examples:", style="bold")
    examples = [
        "readvideo https://www.youtube.com/watch?v=abc123",
        "readvideo --auto-detect https://www.youtube.com/watch?v=abc123",
        "readvideo https://www.bilibili.com/video/BV1234567890",
        "readvideo ~/Music/podcast.mp3",
        "readvideo ~/Videos/lecture.mp4 --output-dir ./transcripts",
    ]

    for example in examples:
        console.print(f"  {example}", style="dim")

    console.print("\n📖 More information:", style="bold")
    console.print(
        "  GitHub: https://github.com/learnerLj/readvideo", style="dim"
    )


# Create CLI group for multiple commands
@click.group()
def cli():
    """ReadVideo - Video and Audio Transcription Tool"""
    pass


# Add single video processing as 'process' command
@cli.command("process")
@click.argument("input_source", required=True)
@click.option(
    "--auto-detect",
    is_flag=True,
    help="Enable automatic language detection (default: Chinese)",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    help="Output directory (default: current directory or input file directory)",
)
@click.option(
    "--no-cleanup", is_flag=True, help="Do not clean up temporary files"
)
@click.option(
    "--info-only",
    is_flag=True,
    help="Show input information only, do not process",
)
@click.option(
    "--whisper-model",
    default="~/.whisper-models/ggml-large-v3.bin",
    help="Path to Whisper model file",
)
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option(
    "--proxy", help="HTTP proxy address (e.g., http://127.0.0.1:8080)"
)
def process_single(
    input_source,
    auto_detect,
    output_dir,
    no_cleanup,
    info_only,
    whisper_model,
    verbose,
    proxy,
):
    """Process single video, audio file or URL."""
    # Call main function directly with correct arguments
    import sys

    # Save original argv and replace it temporarily
    original_argv = sys.argv
    sys.argv = [
        "readvideo",
        input_source,
        *(["--auto-detect"] if auto_detect else []),
        *(["-o", output_dir] if output_dir else []),
        *(["--no-cleanup"] if no_cleanup else []),
        *(["--info-only"] if info_only else []),
        *(
            ["--whisper-model", whisper_model]
            if whisper_model != "~/.whisper-models/ggml-large-v3.bin"
            else []
        ),
        *(["-v"] if verbose else []),
        *(["--proxy", proxy] if proxy else []),
    ]

    try:
        main()
    finally:
        sys.argv = original_argv


# Add user processing command
@cli.command("user")
@click.argument("user_input", required=True)
@click.option(
    "--output-dir",
    "-o",
    required=True,
    type=click.Path(),
    help="Output directory (required for user processing)",
)
@click.option(
    "--start-date",
    help="Start date for video filtering (YYYY-MM-DD format, e.g., 2024-01-15). "
    "Videos published on or after this date will be included. "
    "Date must be between 2005-01-01 and today.",
)
@click.option(
    "--max-videos", type=int, help="Maximum number of videos to process"
)
@click.option(
    "--whisper-model",
    default="~/.whisper-models/ggml-large-v3.bin",
    help="Path to Whisper model file",
)
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def user_command(
    user_input, output_dir, start_date, max_videos, whisper_model, verbose
):
    """Process all videos from a Bilibili user.

    USER_INPUT: Bilibili user UID or space URL

    Examples:
      readvideo user 123456 --output-dir ./user_analysis
      readvideo user https://space.bilibili.com/123456 -o ./output
      readvideo user 123456 -o ./output --start-date 2024-01-15 --max-videos 50

    Date filtering:
      --start-date 2024-01-01  # Include videos from Jan 1, 2024 onwards
      --start-date 2023-12-25  # Include videos from Dec 25, 2023 onwards

    Note: Date must be in YYYY-MM-DD format and between 2005-01-01 and today.
    """
    if not verbose:
        print_banner()

    # Validate start date format if provided
    if start_date:
        is_valid, error_message = validate_date_with_range_check(start_date)
        if not is_valid:
            console.print(f"❌ {error_message}", style="red")
            sys.exit(1)

    # Validate max_videos
    if max_videos is not None and max_videos <= 0:
        console.print("❌ max-videos must be a positive integer", style="red")
        sys.exit(1)

    try:
        # Initialize user handler
        user_handler = BilibiliUserHandler(whisper_model)

        console.print("🎯 Starting user processing...", style="bold cyan")
        if start_date:
            console.print(
                f"📅 Date filter: videos from {start_date}", style="dim"
            )
        if max_videos:
            console.print(f"🔢 Video limit: {max_videos} videos", style="dim")

        # Process user
        result = asyncio.run(
            user_handler.process_user(
                user_input=user_input,
                output_dir=output_dir,
                start_date=start_date,
                max_videos=max_videos,
            )
        )

        if result.get("success", False):
            show_user_results(result, verbose)
        else:
            console.print(
                f"❌ User processing failed: {result.get('error', 'Unknown error')}",
                style="red",
            )
            sys.exit(1)

    except KeyboardInterrupt:
        console.print("\n⚠️ Operation interrupted by user", style="yellow")
        sys.exit(1)
    except Exception as e:
        console.print(f"❌ User processing failed: {e}", style="red")
        if verbose:
            import traceback

            console.print(traceback.format_exc(), style="dim")
        sys.exit(1)


def show_user_results(result: dict, verbose: bool):
    """Show user processing results."""
    console.print("\n🎉 User processing completed!", style="bold green")

    # Create results table
    table = Table(show_header=False, box=None)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")

    user_info = result.get("user_info", {})
    stats = result.get("processing_stats", {})

    # User information
    table.add_row(
        "User",
        f"{user_info.get('name', 'Unknown')} (UID: {user_info.get('uid', 'N/A')})",
    )
    table.add_row("Followers", f"{user_info.get('follower', 0):,}")
    table.add_row("", "")  # Empty row for separation

    # Video statistics
    table.add_row("Total Videos Found", str(stats.get("total_videos", 0)))

    # This run statistics
    processed_this_run = stats.get("processed_videos", 0)
    failed_this_run = stats.get("failed_videos", 0)
    skipped_this_run = stats.get("skipped_videos", 0)

    if processed_this_run > 0 or failed_this_run > 0:
        table.add_row("", "")  # Empty row for separation
        table.add_row("[bold]This Run:", "")
        table.add_row("  Processed", str(processed_this_run))
        table.add_row("  Failed", str(failed_this_run))
        if skipped_this_run > 0:
            table.add_row("  Skipped (already done)", str(skipped_this_run))

        # Show success rate for this run if applicable
        run_success_rate = stats.get("run_success_rate", 0)
        if processed_this_run > 0 or failed_this_run > 0:
            table.add_row("  Success Rate", f"{run_success_rate:.1%}")

    # Overall statistics
    overall_completed = stats.get("overall_completed", 0)
    overall_failed = stats.get("overall_failed", 0)
    overall_completion_rate = stats.get("overall_completion_rate", 0)

    if overall_completed > 0 or overall_failed > 0:
        table.add_row("", "")  # Empty row for separation
        table.add_row("[bold]Overall Progress:", "")
        table.add_row("  Completed", str(overall_completed))
        if overall_failed > 0:
            table.add_row("  Failed", str(overall_failed))
        table.add_row("  Completion Rate", f"{overall_completion_rate:.1%}")

    console.print(table)

    # Show processing details if verbose
    if verbose and result.get("results"):
        console.print("\n📋 Processing details (this run):", style="bold")
        for i, video_result in enumerate(
            result["results"][:5]
        ):  # Show first 5
            video_info = video_result.get("video_info", {})
            status = "✅" if video_result.get("success", False) else "❌"
            console.print(
                f"  {status} {video_info.get('title', 'Unknown')}", style="dim"
            )

        if len(result["results"]) > 5:
            console.print(
                f"  ... and {len(result['results']) - 5} more videos",
                style="dim",
            )


# Add Twitter processing command
@cli.command("twitter")
@click.argument("username", required=True)
@click.option(
    "--output-dir",
    "-o",
    required=True,
    type=click.Path(),
    help="Output directory (required for Twitter processing)",
)
@click.option(
    "--start-date",
    help="Start date for tweet filtering (YYYY-MM-DD format, e.g., 2024-01-15). "
    "Tweets published on or after this date will be included.",
)
@click.option(
    "--end-date",
    help="End date for tweet filtering (YYYY-MM-DD format, e.g., 2024-12-31). "
    "Tweets published on or before this date will be included.",
)
@click.option(
    "--max-pages",
    type=int,
    default=50,
    help="Maximum number of pages to fetch (default: 50)",
)
@click.option(
    "--include-retweets",
    is_flag=True,
    help="Include retweets (default: exclude retweets, only show original content)",
)
@click.option(
    "--include-replies",
    is_flag=True,
    help="Include replies (default: exclude replies)",
)
@click.option(
    "--nitter-url",
    default="http://10.144.0.3:8080",
    help="Nitter instance URL (default: http://10.144.0.3:8080)",
)
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def twitter_command(
    username,
    output_dir,
    start_date,
    end_date,
    max_pages,
    include_retweets,
    include_replies,
    nitter_url,
    verbose,
):
    """Process all tweets from a Twitter user via RSS.

    USERNAME: Twitter username (without @)

    Examples:
      readvideo twitter elonmusk --output-dir ./tweets
      readvideo twitter username -o ./output --start-date 2024-01-01 --max-pages 20
      readvideo twitter user -o ./tweets --start-date 2024-01-01 --end-date 2024-12-31

    Date filtering:
      --start-date 2024-01-01  # Include tweets from Jan 1, 2024 onwards
      --end-date 2024-12-31    # Include tweets until Dec 31, 2024

    Note: Dates must be in YYYY-MM-DD format.
    """
    if not verbose:
        print_banner()

    # Clean username (remove @ if present)
    if username.startswith("@"):
        username = username[1:]

    # Validate date formats if provided
    if start_date:
        is_valid, error_message = validate_date_with_range_check(start_date)
        if not is_valid:
            console.print(f"❌ Start date: {error_message}", style="red")
            sys.exit(1)

    if end_date:
        is_valid, error_message = validate_date_with_range_check(end_date)
        if not is_valid:
            console.print(f"❌ End date: {error_message}", style="red")
            sys.exit(1)

    # Validate max_pages
    if max_pages <= 0:
        console.print("❌ max-pages must be a positive integer", style="red")
        sys.exit(1)

    try:
        # Initialize Twitter handler
        twitter_handler = TwitterHandler(nitter_url)

        console.print("🐦 Starting Twitter processing...", style="bold cyan")
        if start_date:
            console.print(
                f"📅 Start date filter: tweets from {start_date}", style="dim"
            )
        if end_date:
            console.print(
                f"📅 End date filter: tweets until {end_date}", style="dim"
            )
        console.print(f"📄 Page limit: {max_pages} pages", style="dim")

        # Process user tweets
        result = asyncio.run(
            twitter_handler.process_user(
                username=username,
                output_dir=output_dir,
                max_pages=max_pages,
                exclude_retweets=not include_retweets,
                exclude_replies=not include_replies,
                start_date=start_date,
                end_date=end_date,
            )
        )

        if result.get("success", False):
            show_twitter_results(result, verbose)
        else:
            console.print(
                f"❌ Twitter processing failed: {result.get('error', 'Unknown error')}",
                style="red",
            )
            sys.exit(1)

    except KeyboardInterrupt:
        console.print("\n⚠️ Operation interrupted by user", style="yellow")
        sys.exit(1)
    except Exception as e:
        console.print(f"❌ Twitter processing failed: {e}", style="red")
        if verbose:
            import traceback

            console.print(traceback.format_exc(), style="dim")
        sys.exit(1)


def show_twitter_results(result: dict, verbose: bool):
    """Show Twitter processing results."""
    console.print("\n🎉 Twitter processing completed!", style="bold green")

    # Create results table
    table = Table(show_header=False, box=None)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Username", f"@{result.get('username', 'unknown')}")
    table.add_row("Total Tweets", str(result.get("total_tweets", 0)))
    table.add_row("Output Directory", result.get("output_dir", ""))

    output_files = result.get("output_files", {})
    if output_files.get("json"):
        table.add_row("JSON File", output_files["json"])
    if output_files.get("markdown"):
        table.add_row("Markdown File", output_files["markdown"])

    console.print(table)

    if verbose:
        console.print("\n📋 Processing completed successfully", style="dim")


# Add YouTube channel processing command
@cli.command("youtube-channel")
@click.argument("channel_input", required=True)
@click.option(
    "--output-dir",
    "-o",
    required=True,
    type=click.Path(),
    help="Output directory (required for channel processing)",
)
@click.option(
    "--start-date",
    help="Start date for video filtering (YYYY-MM-DD format, e.g., 2024-01-15). "
    "Videos published on or after this date will be included.",
)
@click.option(
    "--max-videos",
    type=int,
    help="Maximum number of videos to process (e.g., --max-videos 50)",
)
@click.option(
    "--whisper-model",
    default="~/.whisper-models/ggml-large-v3.bin",
    help="Path to whisper model file for transcription",
)
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def youtube_channel_command(
    channel_input, output_dir, start_date, max_videos, whisper_model, verbose
):
    """Process all videos from a YouTube channel.

    CHANNEL_INPUT: YouTube channel (@username) or channel URL

    Examples:
      readvideo youtube-channel @PewDiePie --output-dir ./channel_analysis
      readvideo youtube-channel https://www.youtube.com/@username -o ./output
      readvideo youtube-channel @username -o ./output --start-date 2024-01-15 --max-videos 50

    Date filtering:
      --start-date 2024-01-01  # Include videos from Jan 1, 2024 onwards
      --start-date 2023-12-25  # Include videos from Dec 25, 2023 onwards

    Note: Date must be in YYYY-MM-DD format.
    """
    if not verbose:
        print_banner()

    # Validate start date format if provided
    if start_date:
        is_valid, error_message = validate_date_with_range_check(start_date)
        if not is_valid:
            console.print(f"❌ {error_message}", style="red")
            sys.exit(1)

    # Validate max_videos
    if max_videos is not None and max_videos <= 0:
        console.print("❌ max-videos must be a positive integer", style="red")
        sys.exit(1)

    try:
        # Initialize YouTube channel handler
        channel_handler = YouTubeUserHandler(whisper_model)

        console.print(
            "🎯 Starting YouTube channel processing...", style="bold cyan"
        )
        if start_date:
            console.print(
                f"📅 Date filter: videos from {start_date}", style="dim"
            )
        if max_videos:
            console.print(f"🔢 Video limit: {max_videos} videos", style="dim")

        # Process channel
        result = asyncio.run(
            channel_handler.process_channel(
                channel_input=channel_input,
                output_dir=output_dir,
                start_date=start_date,
                max_videos=max_videos,
            )
        )

        if result.get("success", False):
            show_youtube_channel_results(result, verbose)
        else:
            console.print(
                f"❌ Channel processing failed: {result.get('error', 'Unknown error')}",
                style="red",
            )
            sys.exit(1)

    except KeyboardInterrupt:
        console.print("\n⚠️ Operation interrupted by user", style="yellow")
        sys.exit(1)
    except Exception as e:
        console.print(f"❌ Channel processing failed: {e}", style="red")
        if verbose:
            import traceback

            console.print(traceback.format_exc(), style="dim")
        sys.exit(1)


def show_youtube_channel_results(result: dict, verbose: bool):
    """Show YouTube channel processing results."""
    console.print(
        "\n🎉 YouTube channel processing completed!", style="bold green"
    )

    # Create results table
    table = Table(show_header=False, box=None)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")

    channel_info = result.get("channel_info", {})
    run_stats = result.get("run_stats", {})

    table.add_row("Channel", channel_info.get("display_name", "unknown"))
    table.add_row("Total Videos", str(result.get("total_videos", 0)))
    table.add_row(
        "Attempted This Run", str(run_stats.get("attempted_this_run", 0))
    )
    table.add_row(
        "Successful This Run", str(run_stats.get("successful_this_run", 0))
    )
    table.add_row("Failed This Run", str(run_stats.get("failed_this_run", 0)))
    table.add_row(
        "Skipped This Run", str(run_stats.get("skipped_this_run", 0))
    )
    table.add_row("Total Completed", str(run_stats.get("total_completed", 0)))
    table.add_row("Output Directory", result.get("output_dir", ""))

    console.print(table)

    # Show sample results if available
    results = result.get("results", [])
    successful_results = [r for r in results if r.get("success", False)]

    if successful_results and verbose:
        console.print("\n📋 Recent successful transcripts:", style="bold")
        for i, res in enumerate(successful_results[:5]):
            video_info = res.get("video_info", {})
            title = video_info.get("title", "Unknown title")[:50]
            console.print(f"  {i+1}. {title}...", style="green")

        if len(successful_results) > 5:
            console.print(
                f"  ... and {len(successful_results) - 5} more videos",
                style="dim",
            )

    if verbose:
        console.print("\n📋 Processing completed successfully", style="dim")


if __name__ == "__main__":
    cli()
