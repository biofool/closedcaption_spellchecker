#!/usr/bin/env python3
"""
Caption Watermark - Add timestamp watermarks to caption files
"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class WatermarkConfig:
    """Configuration for watermark generation"""
    format: str = "Closed Captions Updated on {timestamp}"
    timestamp_format: str = "%Y-%m-%d-%H"  # YYYY-MM-DD-HH
    duration_seconds: float = 3.0  # How long to display
    gap_seconds: float = 2.0  # Gap after last segment


def generate_watermark_text(
    config: Optional[WatermarkConfig] = None,
    timestamp: Optional[datetime] = None
) -> str:
    """
    Generate watermark text with current timestamp

    Args:
        config: Watermark configuration (uses defaults if None)
        timestamp: Override timestamp (uses now() if None)

    Returns:
        Formatted watermark text
    """
    if config is None:
        config = WatermarkConfig()

    if timestamp is None:
        timestamp = datetime.now()

    ts_str = timestamp.strftime(config.timestamp_format)
    return config.format.format(timestamp=ts_str)


def add_watermark_segment(
    segments: List[Dict],
    config: Optional[WatermarkConfig] = None,
    timestamp: Optional[datetime] = None
) -> List[Dict]:
    """
    Add watermark as the last segment

    Args:
        segments: Existing caption segments
        config: Watermark configuration
        timestamp: Override timestamp

    Returns:
        New list of segments with watermark appended
    """
    if config is None:
        config = WatermarkConfig()

    # Create copy to avoid modifying original
    result = list(segments)

    # Calculate start time (after last segment)
    if segments:
        last_end = max(seg['end'] for seg in segments)
        start = last_end + config.gap_seconds
    else:
        start = 0.0

    end = start + config.duration_seconds

    watermark_segment = {
        'start': start,
        'end': end,
        'text': generate_watermark_text(config, timestamp)
    }

    result.append(watermark_segment)
    return result


def add_watermark_to_json(
    json_path: Path,
    output_path: Optional[Path] = None,
    config: Optional[WatermarkConfig] = None,
    timestamp: Optional[datetime] = None
) -> Path:
    """
    Add watermark to all videos in a JSON batch file

    Args:
        json_path: Input JSON file
        output_path: Output path (modifies in place if None)
        config: Watermark configuration
        timestamp: Override timestamp

    Returns:
        Path to output file
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    for video in data.get('videos', []):
        segments = video.get('segments', [])
        video['segments'] = add_watermark_segment(segments, config, timestamp)

        # Update full_text to include watermark
        texts = [seg['text'] for seg in video['segments']]
        video['full_text'] = ' '.join(texts)

    if output_path is None:
        output_path = json_path

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return output_path


def remove_watermark_segment(segments: List[Dict]) -> List[Dict]:
    """
    Remove watermark segment if present (for comparison tests)

    Identifies watermark by checking if last segment text matches pattern
    """
    if not segments:
        return segments

    last = segments[-1]
    if 'Closed Captions Updated on' in last.get('text', ''):
        return segments[:-1]

    return segments


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Add timestamp watermark to caption files"
    )

    parser.add_argument('json_file', help='Caption JSON file')
    parser.add_argument('--output', '-o', help='Output file (default: modify in place)')
    parser.add_argument('--format', '-f', help='Watermark format string')
    parser.add_argument('--timestamp', '-t', help='Override timestamp (YYYY-MM-DD-HH)')

    args = parser.parse_args()

    config = WatermarkConfig()
    if args.format:
        config.format = args.format

    timestamp = None
    if args.timestamp:
        timestamp = datetime.strptime(args.timestamp, '%Y-%m-%d-%H')

    json_path = Path(args.json_file)
    output_path = Path(args.output) if args.output else None

    if not json_path.exists():
        print(f"Error: File not found: {json_path}")
        return

    result = add_watermark_to_json(json_path, output_path, config, timestamp)
    print(f"Watermark added. Output: {result}")


if __name__ == "__main__":
    main()
