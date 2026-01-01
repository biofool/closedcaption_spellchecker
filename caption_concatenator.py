#!/usr/bin/env python3
"""
Caption Concatenator - Combine caption files into a single document ordered by date
"""

import json
import argparse
import re
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


def extract_date_from_title(title: str) -> Optional[datetime]:
    """
    Extract date from video title.

    Supports various formats commonly found in titles:
    - 2024-01-15, 2024/01/15, 2024.01.15
    - 01-15-2024, 01/15/2024, 01.15.2024
    - Jan 15, 2024 / January 15, 2024
    - 15 Jan 2024 / 15 January 2024
    """
    if not title:
        return None

    # Pattern 1: YYYY-MM-DD, YYYY/MM/DD, YYYY.MM.DD
    match = re.search(r'(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})', title)
    if match:
        try:
            year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
            return datetime(year, month, day)
        except ValueError:
            pass

    # Pattern 2: MM-DD-YYYY, MM/DD/YYYY, MM.DD.YYYY
    match = re.search(r'(\d{1,2})[-/.](\d{1,2})[-/.](20\d{2})', title)
    if match:
        try:
            month, day, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
            return datetime(year, month, day)
        except ValueError:
            pass

    # Pattern 3: Month name DD, YYYY (e.g., "Jan 15, 2024" or "January 15, 2024")
    months = {
        'jan': 1, 'january': 1, 'feb': 2, 'february': 2, 'mar': 3, 'march': 3,
        'apr': 4, 'april': 4, 'may': 5, 'jun': 6, 'june': 6,
        'jul': 7, 'july': 7, 'aug': 8, 'august': 8, 'sep': 9, 'september': 9,
        'oct': 10, 'october': 10, 'nov': 11, 'november': 11, 'dec': 12, 'december': 12
    }

    match = re.search(
        r'(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|'
        r'july?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)'
        r'\s+(\d{1,2})(?:st|nd|rd|th)?,?\s*(20\d{2})',
        title, re.IGNORECASE
    )
    if match:
        try:
            month = months[match.group(1).lower()]
            day = int(match.group(2))
            year = int(match.group(3))
            return datetime(year, month, day)
        except (ValueError, KeyError):
            pass

    # Pattern 4: DD Month YYYY (e.g., "15 Jan 2024" or "15 January 2024")
    match = re.search(
        r'(\d{1,2})(?:st|nd|rd|th)?\s+'
        r'(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|'
        r'july?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)'
        r',?\s*(20\d{2})',
        title, re.IGNORECASE
    )
    if match:
        try:
            day = int(match.group(1))
            month = months[match.group(2).lower()]
            year = int(match.group(3))
            return datetime(year, month, day)
        except (ValueError, KeyError):
            pass

    return None


def get_video_date(video: Dict) -> Optional[datetime]:
    """
    Get the best available date for a video.
    Priority: upload_date > date extracted from title
    """
    # First try the upload_date field
    upload_date = parse_upload_date(video.get('upload_date'))
    if upload_date:
        return upload_date

    # Fall back to extracting from title
    title = video.get('title', '')
    return extract_date_from_title(title)


def format_date_str(date_str: Optional[str]) -> str:
    """Format date string for display"""
    dt = parse_upload_date(date_str)
    if dt:
        return dt.strftime('%Y-%m-%d')
    return 'Unknown date'


def format_video_date(video: Dict) -> str:
    """Format the best available date for a video"""
    dt = get_video_date(video)
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

    # Sort by date (upload_date or extracted from title)
    def sort_key(video):
        dt = get_video_date(video)
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
            date = format_video_date(video)
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
            date = format_video_date(video)
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

  # Output both text and markdown
  python caption_concatenator.py *.json -o combined -f text,markdown

  # Newest videos first
  python caption_concatenator.py *.json -o combined.txt --reverse

  # Text only, no metadata headers
  python caption_concatenator.py *.json -o combined.txt --no-metadata
        """
    )

    parser.add_argument('json_files', nargs='+', type=Path,
                       help='Caption batch JSON files to concatenate')
    parser.add_argument('-o', '--output', type=Path, required=True,
                       help='Output file path (extension added automatically for multiple formats)')
    parser.add_argument('-f', '--format', default='text',
                       help='Output format(s): text, markdown, or both (e.g., "text,markdown")')
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

    # Parse format(s)
    formats = [f.strip().lower() for f in args.format.split(',')]
    valid_formats = {'text', 'markdown'}
    for fmt in formats:
        if fmt not in valid_formats:
            print(f"Error: Invalid format '{fmt}'. Use 'text' or 'markdown'")
            return 1

    # Auto-detect format from output extension if single format not specified
    if len(formats) == 1 and formats[0] == 'text':
        if args.output.suffix.lower() == '.md':
            formats = ['markdown']

    print(f"Processing {len(args.json_files)} file(s)...")

    # Count videos
    total_videos = sum(len(load_batch_file(f)) for f in args.json_files)

    # Generate output for each format
    output_files = []
    format_extensions = {'text': '.txt', 'markdown': '.md'}

    for output_format in formats:
        # Concatenate
        result = concatenate_text(
            args.json_files,
            output_format=output_format,
            include_metadata=not args.no_metadata,
            reverse_order=args.reverse
        )

        # Determine output path
        if len(formats) == 1:
            # Single format: use output path as-is
            output_path = args.output
        else:
            # Multiple formats: add extension to base name
            base = args.output.with_suffix('')  # Remove any existing extension
            output_path = base.with_suffix(format_extensions[output_format])

        # Write output
        output_path.write_text(result, encoding='utf-8')
        output_files.append((output_format, output_path))

    print(f"Concatenated {total_videos} videos")
    for fmt, path in output_files:
        print(f"Output ({fmt}): {path}")
    if args.reverse:
        print("Order: Newest first")
    else:
        print("Order: Oldest first")

    return 0


if __name__ == '__main__':
    exit(main())
