# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A two-application pipeline for bulk-correcting YouTube auto-captions with specialized terminology (e.g., Aikido terms). The workflow:
1. Download captions in batches via `caption_downloader.py`
2. Human edits the `full_text` fields in the output JSON
3. Run `caption_diff_mapper.py` to extract corrections into a terminology mapping
4. Future downloads automatically apply the terminology corrections

## Commands

```bash
# Install dependencies
pip install yt-dlp python-dotenv

# Download captions from a channel (default 16 videos)
python caption_downloader.py --channel "https://www.youtube.com/@YourChannel"

# Download from a playlist
python caption_downloader.py --playlist "https://www.youtube.com/playlist?list=PLxxxxx"

# Download with custom batch size
python caption_downloader.py --channel URL --batch-size 8

# Download multiple batches
python caption_downloader.py --channel URL --batches 2

# Build terminology mappings (automatic)
python caption_diff_mapper.py original.json corrected.json

# Build mappings interactively
python caption_diff_mapper.py original.json corrected.json --interactive

# View current mappings
python caption_diff_mapper.py --view

# Filter mappings by minimum occurrence count
python caption_diff_mapper.py original.json corrected.json --min-count 2
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
```

## Environment Configuration

Set in `.env` file:
- `TERMINOLOGY_MAPPING_FILE`: Path to terminology dictionary (default: `.cache/terminology_mapping.json`)
- `CACHE_DIR`: Directory for downloads and output (default: `.cache`)

## Key Implementation Details

- Caption parsing uses regex to extract VTT/SRT timestamps and clean HTML tags
- Terminology mappings are applied case-insensitively with longest-match-first ordering
- The mapper detects both single-word and multi-word phrase differences (up to 4 words)
- Downloaded caption files are cached in `.cache/captions/` to avoid re-downloading
