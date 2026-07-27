# closedcaption_spellchecker — Technical Marketing Summary

## One-Line Positioning

A batch pipeline for bulk-correcting YouTube auto-captions with specialized terminology, building a self-improving terminology dictionary from your corrections.

## Target Users / Personas

- **YouTube content creators** with channels featuring specialized vocabulary (martial arts, medical, technical) whose auto-captions consistently mistranscribe domain terms.
- **Caption editors and accessibility teams** who need to correct large volumes of auto-generated captions efficiently.
- **Channel managers** overseeing multiple videos who want to apply consistent terminology corrections across all content.

## Key Features (Grounded in Code)

- **Batch caption downloading**: Downloads captions from YouTube channels or playlists in configurable batch sizes via `yt-dlp`, with support for channel URLs, playlist URLs, single videos, and Shorts (`caption_downloader.py`, `CaptionDownloader` class).
- **Terminology mapping with auto-application**: Corrections made in one batch are saved to a terminology dictionary (`terminology_mapping.json`) and automatically applied to future downloads using case-insensitive, longest-match-first replacement (`caption_downloader.py`, `TerminologyMapper` class).
- **Diff-based mapping generation**: Compares original vs. corrected caption text using `difflib.SequenceMatcher` to detect single-word and multi-word phrase differences (up to 4 words), with interactive review mode (`caption_diff_mapper.py`, `CaptionDiffMapper` and `InteractiveMapper` classes).
- **YouTube upload via Data API**: Uploads corrected captions back to YouTube using service account authentication, converting JSON segments to VTT format (`caption_uploader.py`, `CaptionUploader` class).
- **Timestamp watermarking**: Appends a configurable timestamp watermark segment to caption files (default format: "Closed Captions Updated on YYYY-MM-DD-HH") (`caption_watermark.py`, `WatermarkConfig` dataclass).
- **Spell-check tracking GUI**: PySide6 desktop application for viewing and managing spell-check status per video, with filtering by status and date, backup of originals, and export capabilities (`spellcheck_gui.py`, `VideoTableModel` and `VideoFilterProxyModel`).
- **VTT format utilities**: Converts between JSON caption segments and WebVTT format with precise timestamp formatting (`vtt_formatter.py`).
- **Structured JSON output**: Each batch produces a JSON file with timestamped segments and a concatenated `full_text` field for easy editing.

## Technical Differentiators

- **Self-improving dictionary**: The terminology mapping grows over time — each correction batch makes future downloads more accurate automatically, reducing manual effort progressively.
- **Longest-match-first ordering**: Prevents partial-match errors when applying terminology corrections (e.g., "tai no henko" is matched before "tai" alone).
- **Multi-word phrase detection**: The diff mapper detects compound terms that get split across caption segments, not just single-word substitutions.
- **Interactive and automatic modes**: Users can review each correction interactively (y/n/e/s/q commands) or let the mapper generate all mappings automatically with a minimum occurrence threshold.
- **Original backup tracking**: Automatically backs up original captions to an `originals/` directory and tracks spell-check status in a committed JSON file for auditability.

## Use Cases

- Correcting Aikido terminology in a YouTube channel's auto-captions (e.g., "a key doe" → "Aikido", "ten con" → "tenkan").
- Building a domain-specific terminology dictionary for any specialized field that YouTube's speech recognition handles poorly.
- Batch-processing hundreds of videos with consistent corrections applied automatically.
- Adding timestamp watermarks to caption files to indicate when they were last updated.

## Benefits / Value Proposition

- Correct once, benefit forever: terminology corrections compound over time as the dictionary grows.
- Reduces caption correction effort from per-video manual editing to batch-level review.
- Provides a complete workflow from download to correction to re-upload, all in one toolset.
- Maintains audit trail with original backups and spell-check status tracking.

## Tech Stack

- **Language**: Python 3.8+
- **Caption download**: `yt-dlp`
- **YouTube API**: `google-api-python-client`, `google-auth` (service account)
- **GUI**: `PySide6`
- **Document export**: `python-docx`, `fpdf2`
- **Testing**: `pytest`, `pytest-mock`
- **Config**: `python-dotenv` (`.env` file)

## Known Limitations

- YouTube upload requires a Google Cloud service account with channel manager permissions.
- Terminology mapping is applied as simple text replacement — it cannot handle context-dependent corrections.
- The diff mapper detects differences up to 4-word phrases; longer phrase corrections may not be captured automatically.
- Requires `ffmpeg`/`ffprobe` installed as system binaries for yt-dlp post-processing.
- A JavaScript runtime (Deno, Node.js, or Bun) is recommended for yt-dlp to handle YouTube's anti-bot measures.
