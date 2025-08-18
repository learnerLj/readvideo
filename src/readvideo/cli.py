"""Command line interface for readvideo."""

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
from .user_content.utils import validate_date_format

console = Console()


def print_banner():
    """Print application banner."""
    banner = """
[bold cyan]ReadVideo[/bold cyan] - Video & Audio Transcription Tool

Supported Platforms:
  • [green]YouTube[/green] - Prioritize existing subtitles, fallback to audio transcription
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
@click.option("--no-cleanup", is_flag=True, help="Do not clean up temporary files")
@click.option(
    "--info-only", is_flag=True, help="Show input information only, do not process"
)
@click.option(
    "--whisper-model",
    default="~/.whisper-models/ggml-large-v3.bin",
    help="Path to Whisper model file",
)
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option("--proxy", help="HTTP proxy address (e.g., http://127.0.0.1:8080)")
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
                    "Has Transcripts", "Yes" if info.get("has_transcripts") else "No"
                )

                transcripts = info.get("available_transcripts", {})
                if transcripts.get("manual"):
                    languages = [t["language"] for t in transcripts["manual"]]
                    table.add_row("Manual Subtitles", ", ".join(languages))
                if transcripts.get("generated"):
                    languages = [t["language"] for t in transcripts["generated"]]
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
        "Transcript" if result.get("method") == "transcript" else "Audio Transcription",
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
            f"\n🗑️ Temporary files: {len(result['temp_files'])} cleaned up", style="dim"
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
    console.print("  GitHub: https://github.com/learnerLj/readvideo", style="dim")


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
@click.option("--no-cleanup", is_flag=True, help="Do not clean up temporary files")
@click.option(
    "--info-only", is_flag=True, help="Show input information only, do not process"
)
@click.option(
    "--whisper-model",
    default="~/.whisper-models/ggml-large-v3.bin",
    help="Path to Whisper model file",
)
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option("--proxy", help="HTTP proxy address (e.g., http://127.0.0.1:8080)")
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
@click.option("--start-date", help="Start date for video filtering (YYYY-MM-DD format)")
@click.option("--max-videos", type=int, help="Maximum number of videos to process")
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
      readvideo user 123456 -o ./output --start-date 2024-01-01 --max-videos 50
    """
    if not verbose:
        print_banner()

    # Validate start date format if provided
    if start_date and not validate_date_format(start_date):
        console.print(
            f"❌ Invalid date format: {start_date}. Use YYYY-MM-DD format.", style="red"
        )
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
            console.print(f"📅 Date filter: videos from {start_date}", style="dim")
        if max_videos:
            console.print(f"🔢 Video limit: {max_videos} videos", style="dim")

        # Process user
        result = user_handler.process_user(
            user_input=user_input,
            output_dir=output_dir,
            start_date=start_date,
            max_videos=max_videos,
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
        for i, video_result in enumerate(result["results"][:5]):  # Show first 5
            video_info = video_result.get("video_info", {})
            status = "✅" if video_result.get("success", False) else "❌"
            console.print(
                f"  {status} {video_info.get('title', 'Unknown')}", style="dim"
            )

        if len(result["results"]) > 5:
            console.print(
                f"  ... and {len(result['results']) - 5} more videos", style="dim"
            )


if __name__ == "__main__":
    cli()
