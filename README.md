# YouTube Caption Cleanup Pipeline

A two-application workflow for bulk-correcting YouTube auto-captions with specialized terminology (like Aikido terms).

## The Problem

YouTube's auto-captioning consistently mangles specialized vocabulary. Instead of fixing each video manually, this pipeline lets you:

1. **Download** captions in batches
2. **Correct** them once as a group
3. **Build** a terminology dictionary from your corrections
4. **Apply** that dictionary automatically to future batches

## Installation

```bash
pip install -r requirements.txt
```

Or manually:
```bash
pip install yt-dlp python-dotenv google-api-python-client google-auth pytest
```

## Quick Start

### 1. Configure Environment

```bash
cp .env.example .env
# Edit .env to set your paths
```

### 2. Download Captions (First Batch)

```bash
# Download 16 most recent videos from your channel
python caption_downloader.py --channel "https://www.youtube.com/@YourChannel"

# Or from a playlist
python caption_downloader.py --playlist "https://www.youtube.com/playlist?list=PLxxxxx"
```

This creates: `.cache/output/captions_batch_1_YYYYMMDD_HHMMSS.json`

### 3. Spell Check the JSON

1. Open the output JSON file
2. Find the `"full_text"` field for each video
3. Fix the mistranscribed terms (e.g., "a key doe" → "Aikido")
4. Save as a new file (e.g., `captions_batch_1_corrected.json`)

### 4. Build Terminology Mappings

```bash
# Compare original and corrected files
python caption_diff_mapper.py .cache/output/captions_batch_1_*.json captions_batch_1_corrected.json

# Or use interactive mode to review each difference
python caption_diff_mapper.py original.json corrected.json --interactive
```

This creates/updates: `.cache/terminology_mapping.json`

### 5. Download Next Batch (Mappings Applied Automatically)

```bash
python caption_downloader.py --channel "https://www.youtube.com/@YourChannel"
```

The mappings are now automatically applied as captions are downloaded!

---

## App 1: caption_downloader.py

Downloads captions and concatenates them for batch spell checking.

### Usage

```bash
# Basic usage
python caption_downloader.py --channel "https://www.youtube.com/@YourChannel"
python caption_downloader.py --playlist "https://www.youtube.com/playlist?list=PLxxxxx"

# Custom batch size
python caption_downloader.py --channel URL --batch-size 8

# Multiple batches (e.g., 32 videos in 2 batches)
python caption_downloader.py --channel URL --batches 2

# Specify output file
python caption_downloader.py --channel URL --output my_captions.json
```

### Output Format

```json
{
  "batch_number": 1,
  "batch_size": 16,
  "created_at": "2025-01-15T10:30:00",
  "mapping_applied": true,
  "mapping_file": ".cache/terminology_mapping.json",
  "videos": [
    {
      "video_id": "abc123xyz",
      "title": "Aikido Class - Irimi Tenkan",
      "url": "https://www.youtube.com/watch?v=abc123xyz",
      "upload_date": "20250110",
      "segments": [
        {"start": 0.0, "end": 2.5, "text": "Welcome to the dojo"},
        {"start": 2.5, "end": 5.0, "text": "Today we practice irimi"}
      ],
      "full_text": "Welcome to the dojo Today we practice irimi..."
    }
  ]
}
```

**Tip:** Edit the `full_text` field for each video - it's the concatenated caption text for easy spell checking.

---

## App 2: caption_diff_mapper.py

Compares original and spell-checked JSON to build terminology mappings.

### Usage

```bash
# Automatic mode - generates all mappings
python caption_diff_mapper.py original.json corrected.json

# Interactive mode - review each difference
python caption_diff_mapper.py original.json corrected.json --interactive

# Only include terms appearing 2+ times
python caption_diff_mapper.py original.json corrected.json --min-count 2

# View current mappings
python caption_diff_mapper.py --view

# Custom output file
python caption_diff_mapper.py original.json corrected.json -o aikido_terms.json
```

### Interactive Mode Commands

- `y` - Yes, add this mapping
- `n` - No, skip this one
- `e` - Edit the mapping before adding
- `s` - Skip all remaining differences
- `q` - Quit review

### Mapping File Format

```json
{
  "version": "1.0",
  "updated_at": "2025-01-15T10:30:00",
  "total_mappings": 25,
  "description": "Aikido terminology corrections for YouTube auto-captions",
  "mappings": {
    "a key doe": "Aikido",
    "eye key doe": "Aikido",
    "ear ream e": "irimi",
    "ten con": "tenkan"
  }
}
```

---

## App 3: caption_uploader.py

Uploads corrected captions back to YouTube using the YouTube Data API.

### Prerequisites

1. Create a Google Cloud project
2. Enable the YouTube Data API v3
3. Create a service account and download the JSON key
4. Add the service account as a manager on your YouTube channel

### Usage

```bash
# Upload all videos from a batch file
python caption_uploader.py captions_batch_1.json

# Upload only a specific video
python caption_uploader.py captions_batch_1.json --video abc123xyz

# Dry run to see what would be uploaded
python caption_uploader.py captions_batch_1.json --dry-run
```

---

## App 4: caption_watermark.py

Adds a timestamp watermark to caption files (appears at the end of captions).

### Usage

```bash
# Add watermark to a caption file (modifies in place)
python caption_watermark.py captions_batch_1.json

# Save to a different file
python caption_watermark.py captions_batch_1.json -o watermarked.json

# Custom timestamp
python caption_watermark.py captions_batch_1.json -t 2025-01-15-14
```

The watermark format is: `Closed Captions Updated on YYYY-MM-DD-HH`

---

## Testing

```bash
# Run unit tests
pytest

# Run all tests including integration tests (requires credentials)
pytest --run-integration

# Run specific test file
pytest tests/test_caption_watermark.py -v
```

---

## Environment Variables

Set these in your `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `TERMINOLOGY_MAPPING_FILE` | `.cache/terminology_mapping.json` | Path to terminology dictionary |
| `CACHE_DIR` | `.cache` | Directory for downloads and output |
| `BATCH_SIZE` | `8` | Default videos per batch |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | - | Path to service account JSON key |
| `TEST_VIDEO_ID` | - | Video ID for integration tests |

---

## Workflow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     INITIAL SETUP                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  caption_downloader.py ──► batch_1.json ──► (human edits) ──►   │
│                                             batch_1_corrected   │
│                                                   │              │
│  caption_diff_mapper.py ◄─────────────────────────┘              │
│           │                                                      │
│           ▼                                                      │
│  terminology_mapping.json                                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     SUBSEQUENT BATCHES                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  terminology_mapping.json ──► caption_downloader.py ──►          │
│         (auto-applied)              │                            │
│                                     ▼                            │
│                              batch_N.json                        │
│                          (already corrected!)                    │
│                                     │                            │
│                              (human review)                      │
│                                     │                            │
│                              any new fixes? ──► caption_diff_mapper.py
│                                                       │          │
│                                                       ▼          │
│                              terminology_mapping.json (updated)  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Tips

1. **Start with a small batch** - Use `--batch-size 4` for your first run to test the workflow

2. **Review interactively first** - Use `--interactive` mode until you're confident in the auto-detection

3. **Common Aikido mistranscriptions** - See `terminology_mapping_example.json` for a starter dictionary

4. **Compound terms** - The mapper detects multi-word phrases like "tai no henko" that get split up

5. **Case handling** - Mappings are applied case-insensitively; corrections preserve the specified case

---

## File Structure

```
.
├── caption_downloader.py      # App 1: Download and concatenate
├── caption_diff_mapper.py     # App 2: Diff and build mappings
├── caption_uploader.py        # App 3: Upload to YouTube
├── caption_watermark.py       # App 4: Add timestamp watermarks
├── vtt_formatter.py           # VTT format conversion utility
├── requirements.txt           # Python dependencies
├── pytest.ini                 # Test configuration
├── .env                       # Configuration
├── .env.example               # Configuration template
├── terminology_mapping_example.json  # Starter dictionary
├── tests/                     # Test suite
│   ├── conftest.py
│   ├── test_vtt_formatter.py
│   ├── test_caption_watermark.py
│   ├── test_caption_uploader.py
│   └── test_round_trip.py
└── .cache/
    ├── captions/              # Downloaded VTT files
    ├── output/                # JSON batch files
    ├── logs/                  # Debug logs
    └── terminology_mapping.json  # Your corrections dictionary
```
