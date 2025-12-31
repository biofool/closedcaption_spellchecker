#!/usr/bin/env python3
"""
VTT Formatter - Convert JSON caption segments to WebVTT format
"""

import json
from pathlib import Path
from typing import List, Dict


def seconds_to_vtt_timestamp(seconds: float) -> str:
    """
    Convert seconds to VTT timestamp format (HH:MM:SS.mmm)

    Args:
        seconds: Time in seconds (float)

    Returns:
        VTT timestamp string
    """
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    millis = int((seconds - total_seconds) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def segments_to_vtt(segments: List[Dict]) -> str:
    """
    Convert caption segments to VTT format string

    Args:
        segments: List of dicts with 'start', 'end', 'text' keys

    Returns:
        VTT format string
    """
    lines = ["WEBVTT", ""]

    for i, segment in enumerate(segments, 1):
        start = seconds_to_vtt_timestamp(segment['start'])
        end = seconds_to_vtt_timestamp(segment['end'])
        text = segment['text']

        lines.append(str(i))
        lines.append(f"{start} --> {end}")
        lines.append(text)
        lines.append("")

    return "\n".join(lines)


def save_vtt(segments: List[Dict], output_path: Path) -> Path:
    """
    Save segments as VTT file

    Args:
        segments: Caption segments
        output_path: Path for output file

    Returns:
        Path to saved file
    """
    vtt_content = segments_to_vtt(segments)
    output_path.write_text(vtt_content, encoding='utf-8')
    return output_path


def load_json_captions(json_path: Path) -> Dict:
    """
    Load captions from JSON file

    Args:
        json_path: Path to JSON file

    Returns:
        Parsed JSON data
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)
