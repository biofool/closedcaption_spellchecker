#!/usr/bin/env python3
"""
Caption Concatenator - Combine caption files into a single document ordered by date
"""

import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional


def load_batch_file(json_path: Path) -> List[Dict]:
    """Load videos from a caption batch JSON file"""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('videos', [])


def parse_upload_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse upload date string to datetime"""
    if not date_str:
        return None

    # Try various formats with their expected string lengths
    formats = [
        ('%Y%m%d', 8),              # 20240115
        ('%Y-%m-%d', 10),           # 2024-01-15
        ('%Y-%m-%dT%H:%M:%S', 19),  # ISO format
    ]

    for fmt, length in formats:
        try:
            return datetime.strptime(date_str[:length], fmt)
        except (ValueError, TypeError):
            continue

    return None


def format_date(date_str: Optional[str]) -> str:
    """Format date string for display"""
    dt = parse_upload_date(date_str)
    if dt:
        return dt.strftime('%Y-%m-%d')
    return 'Unknown date'


def concatenate_text(
    json_files: List[Path],
    output_format: str = 'text',
    include_metadata: bool = True,
    reverse_order: bool = False
) -> str:
    """
    Concatenate full text from all videos in JSON files.

    Args:
        json_files: List of caption batch JSON files
        output_format: 'text' or 'markdown'
        include_metadata: Include video title, URL, date
        reverse_order: If True, newest first; otherwise oldest first

    Returns:
        Concatenated text
    """
    # Collect all videos
    all_videos = []
    for json_path in json_files:
        videos = load_batch_file(json_path)
        all_videos.extend(videos)

    # Sort by upload date
    def sort_key(video):
        dt = parse_upload_date(video.get('upload_date'))
        if dt:
            return dt
        # Put videos without dates at the end
        return datetime.max if not reverse_order else datetime.min

    all_videos.sort(key=sort_key, reverse=reverse_order)

    # Build output
    lines = []

    if output_format == 'markdown':
        lines.append('# Combined Captions')
        lines.append('')
        lines.append(f'*Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}*')
        lines.append(f'*Total videos: {len(all_videos)}*')
        lines.append('')

        for video in all_videos:
            title = video.get('title', 'Untitled')
            url = video.get('url', '')
            date = format_date(video.get('upload_date'))
            full_text = video.get('full_text', '')

            if include_metadata:
                lines.append(f'## {title}')
                lines.append('')
                lines.append(f'**Date:** {date}  ')
                lines.append(f'**URL:** {url}')
                lines.append('')

            lines.append(full_text)
            lines.append('')
            lines.append('---')
            lines.append('')

    else:  # Plain text
        width = 80
        lines.append('=' * width)
        lines.append('COMBINED CAPTIONS')
        lines.append(f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}')
        lines.append(f'Total videos: {len(all_videos)}')
        lines.append('=' * width)
        lines.append('')

        for video in all_videos:
            title = video.get('title', 'Untitled')
            url = video.get('url', '')
            date = format_date(video.get('upload_date'))
            full_text = video.get('full_text', '')

            if include_metadata:
                lines.append('=' * width)
                lines.append(f'Video: {title}')
                lines.append(f'Date: {date}')
                lines.append(f'URL: {url}')
                lines.append('=' * width)
                lines.append('')

            lines.append(full_text)
            lines.append('')
            lines.append('')

    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(
        description='Concatenate caption files into a single document ordered by upload date',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Concatenate from a single batch file
  python caption_concatenator.py captions_batch_1.json -o combined.txt

  # Concatenate from multiple batch files
  python caption_concatenator.py batch1.json batch2.json batch3.json -o combined.txt

  # Output as markdown
  python caption_concatenator.py *.json -o combined.md --format markdown

  # Newest videos first
  python caption_concatenator.py *.json -o combined.txt --reverse

  # Text only, no metadata headers
  python caption_concatenator.py *.json -o combined.txt --no-metadata
        """
    )

    parser.add_argument('json_files', nargs='+', type=Path,
                       help='Caption batch JSON files to concatenate')
    parser.add_argument('-o', '--output', type=Path, required=True,
                       help='Output file path')
    parser.add_argument('-f', '--format', choices=['text', 'markdown'],
                       default='text', help='Output format (default: text)')
    parser.add_argument('--reverse', action='store_true',
                       help='Reverse order (newest first)')
    parser.add_argument('--no-metadata', action='store_true',
                       help='Exclude video titles, URLs, and dates')

    args = parser.parse_args()

    # Validate input files exist
    for json_file in args.json_files:
        if not json_file.exists():
            print(f"Error: File not found: {json_file}")
            return 1

    # Auto-detect format from output extension
    output_format = args.format
    if args.output.suffix.lower() == '.md':
        output_format = 'markdown'

    print(f"Processing {len(args.json_files)} file(s)...")

    # Concatenate
    result = concatenate_text(
        args.json_files,
        output_format=output_format,
        include_metadata=not args.no_metadata,
        reverse_order=args.reverse
    )

    # Count videos
    total_videos = sum(len(load_batch_file(f)) for f in args.json_files)

    # Write output
    args.output.write_text(result, encoding='utf-8')

    print(f"Concatenated {total_videos} videos")
    print(f"Output: {args.output}")
    print(f"Format: {output_format}")
    if args.reverse:
        print("Order: Newest first")
    else:
        print("Order: Oldest first")

    return 0


if __name__ == '__main__':
    exit(main())
