# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A pipeline for bulk-correcting YouTube auto-captions with specialized terminology (e.g., Aikido terms). The workflow:
1. Download captions in batches via `caption_downloader.py`
2. Human edits the `full_text` fields in the output JSON
3. Run `caption_diff_mapper.py` to extract corrections into a terminology mapping
4. Future downloads automatically apply the terminology corrections
5. Optionally add timestamp watermarks via `caption_watermark.py`
6. Upload corrected captions back to YouTube via `caption_uploader.py`

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Download captions from a channel (default 16 videos)
python caption_downloader.py --channel "https://www.youtube.com/@YourChannel"

# Download from a playlist
python caption_downloader.py --playlist "https://www.youtube.com/playlist?list=PLxxxxx"

# Download with custom batch size
python caption_downloader.py --channel URL --batch-size 8

# Build terminology mappings (automatic)
python caption_diff_mapper.py original.json corrected.json

# Build mappings interactively
python caption_diff_mapper.py original.json corrected.json --interactive

# View current mappings
python caption_diff_mapper.py --view

# Add timestamp watermark to captions
python caption_watermark.py captions.json

# Upload captions to YouTube
python caption_uploader.py captions.json

# Upload specific video only
python caption_uploader.py captions.json --video abc123xyz

# Run tests
pytest

# Run integration tests (requires YouTube API credentials)
pytest --run-integration
```

## Architecture

### caption_downloader.py
- `CaptionDownloader`: Main class that fetches video lists, downloads VTT/SRT caption files, and parses them
- `TerminologyMapper`: Loads terminology mappings from JSON and applies case-insensitive replacements (longest-first to avoid partial matches)
- Outputs a structured JSON batch file with `segments` (timestamped) and `full_text` (concatenated for editing)

### caption_diff_mapper.py
- `CaptionDiffMapper`: Compares original vs corrected JSON using `difflib.SequenceMatcher` to find word and phrase differences
- `InteractiveMapper`: CLI interface for reviewing each difference with y/n/e/s/q commands
- Merges new mappings with existing ones (case-insensitive deduplication)

### caption_uploader.py
- `CaptionUploader`: Uploads captions to YouTube via Data API using service account authentication
- Converts JSON segments to VTT format for upload
- Supports replacing existing captions or adding new tracks

### caption_watermark.py
- `WatermarkConfig`: Dataclass for watermark settings (format, duration, gap)
- `add_watermark_segment()`: Appends timestamp watermark at end of captions
- `add_watermark_to_json()`: Processes batch JSON files

### vtt_formatter.py
- `seconds_to_vtt_timestamp()`: Converts float seconds to VTT timestamp format
- `segments_to_vtt()`: Converts JSON segments to WebVTT string
- Used by uploader to generate VTT files for YouTube

### Data Flow
```
Channel/Playlist URL
       ↓
caption_downloader.py (applies existing mappings)
       ↓
.cache/output/captions_batch_N.json
       ↓
Human edits full_text fields → corrected.json
       ↓
caption_diff_mapper.py
       ↓
.cache/terminology_mapping.json (grows over time)
       ↓
caption_watermark.py (optional - adds timestamp)
       ↓
caption_uploader.py (uploads to YouTube)
```

## Environment Configuration

Set in `.env` file:
- `TERMINOLOGY_MAPPING_FILE`: Path to terminology dictionary (default: `.cache/terminology_mapping.json`)
- `CACHE_DIR`: Directory for downloads and output (default: `.cache`)
- `GOOGLE_SERVICE_ACCOUNT_FILE`: Path to service account JSON for YouTube API
- `TEST_VIDEO_ID`: Video ID for integration tests

## Key Implementation Details

- Caption parsing uses regex to extract VTT/SRT timestamps and clean HTML tags
- Terminology mappings are applied case-insensitively with longest-match-first ordering
- The mapper detects both single-word and multi-word phrase differences (up to 4 words)
- Downloaded caption files are cached in `.cache/captions/` to avoid re-downloading
- YouTube upload requires service account with channel manager permissions
- Watermark is placed at end of captions with configurable gap (default 2s) and duration (default 3s)
