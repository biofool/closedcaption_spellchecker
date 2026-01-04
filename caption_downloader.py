#!/usr/bin/env python3
"""
Caption Downloader - Download and concatenate YouTube captions for batch spell checking
Author: Claude
Description: Downloads captions from recent videos in groups of 16, applies terminology 
             mapping, and outputs JSON for human review.
"""

import os
import sys
import json
import re
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import tracker (after load_dotenv so env vars are available)
from spellcheck_tracker import SpellcheckTracker

# ============================================================================
# CONFIGURATION
# ============================================================================
CACHE_DIR = Path(os.getenv("CACHE_DIR", ".cache"))
CAPTIONS_DIR = CACHE_DIR / "captions"
OUTPUT_DIR = CACHE_DIR / "output"
LOG_DIR = CACHE_DIR / "logs"

# Terminology mapping file from .env
MAPPING_FILE = Path(os.getenv("TERMINOLOGY_MAPPING_FILE", ".cache/terminology_mapping.json"))

# Batch size
BATCH_SIZE =  os.getenv("BATCH_SIZE", 8)

# Create directories
for directory in [CACHE_DIR, CAPTIONS_DIR, OUTPUT_DIR, LOG_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# ============================================================================
# LOGGING
# ============================================================================
LOG_FILE = LOG_DIR / f"downloader_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logger = logging.getLogger("CaptionDownloader")
logger.setLevel(logging.DEBUG)

file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s | %(levelname)-8s | %(funcName)-25s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
))

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))

logger.addHandler(file_handler)
logger.addHandler(console_handler)

# ============================================================================
# IMPORTS
# ============================================================================
try:
    import yt_dlp
except ImportError:
    print("Missing required package: yt-dlp")
    print("Install with: pip install yt-dlp python-dotenv")
    sys.exit(1)


# ============================================================================
# DATA STRUCTURES
# ============================================================================
@dataclass
class VideoInfo:
    """Video metadata"""
    video_id: str
    title: str
    url: str
    duration: float
    upload_date: Optional[str] = None


@dataclass
class CaptionSegment:
    """A single caption segment"""
    start: float
    end: float
    text: str


@dataclass
class VideoCaptions:
    """All captions for a video"""
    video_id: str
    title: str
    url: str
    upload_date: Optional[str]
    segments: List[Dict]
    full_text: str  # Concatenated text for easy spell checking


@dataclass
class CaptionBatch:
    """A batch of videos with their captions"""
    batch_number: int
    batch_size: int
    created_at: str
    mapping_applied: bool
    mapping_file: Optional[str]
    videos: List[Dict]


# ============================================================================
# TERMINOLOGY MAPPING
# ============================================================================
class TerminologyMapper:
    """Handles loading and applying terminology corrections"""
    
    def __init__(self, mapping_file: Path):
        self.mapping_file = mapping_file
        self.mappings: Dict[str, str] = {}
        self.case_insensitive_mappings: Dict[str, Tuple[str, str]] = {}  # lower -> (original_wrong, correct)
        self.load_mappings()
    
    def load_mappings(self) -> bool:
        """Load terminology mappings from JSON file"""
        if not self.mapping_file.exists():
            logger.info(f"Mapping file does not exist: {self.mapping_file}")
            return False
        
        try:
            with open(self.mapping_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle both flat dict and structured format
            if isinstance(data, dict):
                if 'mappings' in data:
                    self.mappings = data['mappings']
                else:
                    self.mappings = data
            
            # Build case-insensitive lookup
            for wrong, correct in self.mappings.items():
                self.case_insensitive_mappings[wrong.lower()] = (wrong, correct)
            
            logger.info(f"Loaded {len(self.mappings)} terminology mappings")
            return len(self.mappings) > 0
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in mapping file: {e}")
            return False
        except Exception as e:
            logger.error(f"Error loading mappings: {e}")
            return False
    
    def apply_mappings(self, text: str) -> str:
        """Apply terminology corrections to text"""
        if not self.mappings:
            return text
        
        result = text
        
        # Sort by length (longest first) to avoid partial replacements
        sorted_mappings = sorted(self.mappings.items(), key=lambda x: len(x[0]), reverse=True)
        
        for wrong, correct in sorted_mappings:
            # Case-insensitive replacement while preserving surrounding text
            pattern = re.compile(re.escape(wrong), re.IGNORECASE)
            result = pattern.sub(correct, result)
        
        return result
    
    def is_empty(self) -> bool:
        """Check if mappings are empty"""
        return len(self.mappings) == 0


# ============================================================================
# YOUTUBE OPERATIONS
# ============================================================================
class CaptionDownloader:
    """Downloads and processes YouTube captions"""

    def __init__(self):
        self.captions_dir = CAPTIONS_DIR
        self.output_dir = OUTPUT_DIR
        self.mapper = TerminologyMapper(MAPPING_FILE)
        self.tracker = SpellcheckTracker()

    @staticmethod
    def detect_url_type(url: str) -> str:
        """
        Auto-detect the type of YouTube URL.

        Returns: 'channel', 'playlist', 'video', or 'unknown'
        """
        url = url.strip()

        # Channel patterns (including YouTube Studio)
        if '/@' in url or '/channel/' in url or '/c/' in url or '/user/' in url:
            return 'channel'

        # Playlist patterns (check before video since URLs can have both)
        if 'playlist?list=' in url:
            return 'playlist'
        if 'studio.youtube.com' in url and 'playlist/' in url:
            return 'playlist'
        # watch?list= without v= is a playlist
        if 'list=' in url and 'watch?v=' not in url:
            return 'playlist'

        # Video patterns (including video+list context which is treated as single video)
        if 'watch?v=' in url or 'youtu.be/' in url or '/shorts/' in url:
            return 'video'

        return 'unknown'

    @staticmethod
    def extract_playlist_id(url: str) -> Optional[str]:
        """
        Extract playlist ID from various YouTube URL formats.

        Supports:
        - https://www.youtube.com/playlist?list=PLxxxxx
        - https://www.youtube.com/watch?v=xxx&list=PLxxxxx
        - https://www.youtube.com/watch?list=PLxxxxx
        - https://studio.youtube.com/playlist/PLxxxxx/videos

        Returns: Playlist ID or None if not found
        """
        url = url.strip()

        # Studio format: studio.youtube.com/playlist/PLxxxxx/...
        match = re.search(r'studio\.youtube\.com/playlist/([A-Za-z0-9_-]+)', url)
        if match:
            return match.group(1)

        # Standard format: list=PLxxxxx
        match = re.search(r'list=([A-Za-z0-9_-]+)', url)
        if match:
            return match.group(1)

        return None

    @staticmethod
    def convert_to_standard_url(url: str) -> str:
        """
        Convert YouTube Studio or other special URLs to standard format.

        This helps yt-dlp handle URLs it might not recognize directly.
        """
        url = url.strip()

        # Convert studio playlist URL to standard format
        if 'studio.youtube.com' in url and 'playlist/' in url:
            playlist_id = CaptionDownloader.extract_playlist_id(url)
            if playlist_id:
                return f'https://www.youtube.com/playlist?list={playlist_id}'

        return url

    def get_single_video(self, video_url: str) -> Optional[VideoInfo]:
        """Get info for a single video"""
        logger.debug(f"Fetching single video info: {video_url}")

        # Extract video ID from various URL formats
        video_id = None
        if 'watch?v=' in video_url:
            match = re.search(r'watch\?v=([A-Za-z0-9_-]{11})', video_url)
            if match:
                video_id = match.group(1)
        elif 'youtu.be/' in video_url:
            match = re.search(r'youtu\.be/([A-Za-z0-9_-]{11})', video_url)
            if match:
                video_id = match.group(1)
        elif '/shorts/' in video_url:
            match = re.search(r'/shorts/([A-Za-z0-9_-]{11})', video_url)
            if match:
                video_id = match.group(1)

        if not video_id:
            logger.error(f"Could not extract video ID from: {video_url}")
            return None

        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'ignoreerrors': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)

                if info is None:
                    return None

                return VideoInfo(
                    video_id=info.get('id', video_id),
                    title=info.get('title', 'Unknown'),
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    duration=info.get('duration', 0) or 0,
                    upload_date=info.get('upload_date')
                )
        except Exception as e:
            logger.error(f"Error fetching video {video_url}: {e}")
            return None

    def get_videos_from_urls(
        self,
        urls: List[str],
        max_per_source: int = 100,
        force_playlist: bool = False
    ) -> List[VideoInfo]:
        """
        Get videos from a list of URLs (channels, playlists, or videos).
        Auto-detects URL type and deduplicates results.

        Args:
            urls: List of YouTube URLs
            max_per_source: Maximum videos per source
            force_playlist: If True, treat video+list URLs as playlists
        """
        all_videos = []
        seen_ids = set()

        for url in urls:
            url = url.strip()
            if not url or url.startswith('#'):
                continue

            # Convert special URLs (e.g., Studio) to standard format
            url = self.convert_to_standard_url(url)

            # Detect URL type
            url_type = self.detect_url_type(url)

            # Force playlist mode: if URL has a list parameter, extract as playlist
            if force_playlist and url_type == 'video' and 'list=' in url:
                playlist_id = self.extract_playlist_id(url)
                if playlist_id:
                    url = f'https://www.youtube.com/playlist?list={playlist_id}'
                    url_type = 'playlist'
                    logger.info(f"Forcing playlist mode for: {url[:60]}...")

            logger.info(f"Processing {url_type}: {url[:60]}...")

            try:
                if url_type == 'channel':
                    videos = self.get_channel_videos(url, max_per_source)
                elif url_type == 'playlist':
                    videos = self.get_playlist_videos(url, max_per_source)
                elif url_type == 'video':
                    video = self.get_single_video(url)
                    videos = [video] if video else []
                else:
                    logger.warning(f"Unknown URL type, skipping: {url}")
                    continue

                # Deduplicate
                for video in videos:
                    if video.video_id not in seen_ids:
                        seen_ids.add(video.video_id)
                        all_videos.append(video)

            except Exception as e:
                logger.error(f"Error processing {url}: {e}")
                continue

        logger.info(f"Total unique videos collected: {len(all_videos)}")
        return all_videos

    def get_channel_videos(self, channel_url: str, max_videos: int = 16) -> List[VideoInfo]:
        """Get recent videos from a channel"""
        logger.info(f"Fetching up to {max_videos} videos from channel")
        
        # Handle various channel URL formats
        if '/channel/' in channel_url or '/c/' in channel_url or '/@' in channel_url:
            # Append /videos if not present
            if not channel_url.endswith('/videos'):
                channel_url = channel_url.rstrip('/') + '/videos'
        
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'playlistend': max_videos,
            'ignoreerrors': True,
        }
        
        videos = []
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(channel_url, download=False)
                
                if info is None:
                    logger.error("yt-dlp returned None")
                    return []
                
                entries = info.get('entries', [])
                if entries is None:
                    entries = []
                
                entries = list(entries)  # Convert generator
                logger.info(f"Found {len(entries)} videos")
                
                for entry in entries:
                    if entry is None:
                        continue
                    
                    # Skip unavailable videos
                    title = entry.get('title', '')
                    if '[Private' in title or '[Unavailable' in title or '[Deleted' in title:
                        continue
                    
                    video_id = entry.get('id', '')
                    if not video_id:
                        continue
                    
                    videos.append(VideoInfo(
                        video_id=video_id,
                        title=title,
                        url=f"https://www.youtube.com/watch?v={video_id}",
                        duration=entry.get('duration', 0) or 0,
                        upload_date=entry.get('upload_date')
                    ))
                
            except Exception as e:
                logger.error(f"Error fetching channel: {e}")
                raise
        
        logger.info(f"Returning {len(videos)} valid videos")
        return videos[:max_videos]
    
    def get_playlist_videos(self, playlist_url: str, max_videos: int = 16) -> List[VideoInfo]:
        """Get videos from a playlist"""
        logger.info(f"Fetching up to {max_videos} videos from playlist")
        
        # Handle YouTube Studio URLs
        if 'studio.youtube.com' in playlist_url:
            match = re.search(r'playlist/([A-Za-z0-9_-]+)', playlist_url)
            if match:
                playlist_id = match.group(1)
                playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
        
        ydl_opts = {
            'quiet': True,
            'extract_flat': 'in_playlist',
            'playlistend': max_videos,
            'ignoreerrors': True,
        }
        
        videos = []
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(playlist_url, download=False)
                
                if info is None:
                    return []
                
                entries = list(info.get('entries', []) or [])
                
                for entry in entries:
                    if entry is None:
                        continue
                    
                    title = entry.get('title', '')
                    if '[Private' in title or '[Unavailable' in title:
                        continue
                    
                    video_id = entry.get('id', '')
                    if not video_id:
                        continue
                    
                    videos.append(VideoInfo(
                        video_id=video_id,
                        title=title,
                        url=f"https://www.youtube.com/watch?v={video_id}",
                        duration=entry.get('duration', 0) or 0,
                        upload_date=entry.get('upload_date')
                    ))
                    
            except Exception as e:
                logger.error(f"Error fetching playlist: {e}")
                raise
        
        return videos[:max_videos]
    
    def download_captions(self, video: VideoInfo) -> Optional[Path]:
        """Download captions for a single video"""
        logger.debug(f"Downloading captions for: {video.video_id}")

        # Check for existing caption file
        for ext in ['.en.vtt', '.en.srt']:
            existing = self.captions_dir / f"{video.video_id}{ext}"
            if existing.exists():
                logger.debug(f"Using cached captions: {existing}")
                # Backup original if not already done
                self.tracker.backup_original(video.video_id, existing)
                return existing

        ydl_opts = {
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en'],
            'skip_download': True,
            'outtmpl': str(self.captions_dir / video.video_id),
            'quiet': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video.url])

            # Find the downloaded file
            for pattern in [f"{video.video_id}.en*.vtt", f"{video.video_id}.en*.srt",
                          f"{video.video_id}*.vtt", f"{video.video_id}*.srt"]:
                matches = list(self.captions_dir.glob(pattern))
                if matches:
                    caption_file = matches[0]
                    # Backup original BEFORE any processing
                    self.tracker.backup_original(video.video_id, caption_file)
                    return caption_file

            logger.warning(f"No captions found for {video.video_id}")
            return None

        except Exception as e:
            logger.error(f"Error downloading captions for {video.video_id}: {e}")
            return None
    
    def parse_vtt(self, caption_file: Path) -> List[Dict]:
        """Parse VTT/SRT caption file"""
        try:
            with open(caption_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Failed to read {caption_file}: {e}")
            return []
        
        # Parse timestamps
        pattern = r'(\d{2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})[^\n]*\n(.*?)(?=\n\n|\n\d{2}:\d{2}:\d{2}|\Z)'
        matches = re.findall(pattern, content, re.DOTALL)
        
        segments = []
        for start_time, end_time, text in matches:
            # Clean text
            clean_text = re.sub(r'<[^>]*>', '', text)
            clean_text = clean_text.replace('\n', ' ').strip()
            
            # Skip empty or sound-only segments
            if not clean_text or re.match(r'^\s*\[[^]]+]\s*$', clean_text):
                continue
            
            segments.append({
                'start': self._time_to_seconds(start_time.replace(',', '.')),
                'end': self._time_to_seconds(end_time.replace(',', '.')),
                'text': clean_text
            })
        
        # Deduplicate using smart rolling caption detection
        deduped = self._deduplicate_rolling_captions(segments)

        return deduped

    def _deduplicate_rolling_captions(self, segments: List[Dict]) -> List[Dict]:
        """
        Remove duplicates caused by YouTube's 2-line rolling caption style.

        YouTube exports captions where each timing block shows 2 lines, and the
        timing overlaps. This causes text to appear multiple times:
        - "Okay. So, Shane,"
        - "Okay. So, Shane, um, push on me a little bit."
        - "um, push on me a little bit."

        This method detects and removes these overlapping duplicates.
        """
        if not segments:
            return []

        # Pass 0: Remove very short segments (< 0.25s) whose text is contained in next segment
        # These are "transition" segments from YouTube's rolling caption export
        stage0 = []
        i = 0
        while i < len(segments):
            seg = segments[i]
            duration = seg['end'] - seg['start']

            # Check if this is a very short segment
            if duration < 0.25 and i + 1 < len(segments):
                next_seg = segments[i + 1]
                current_text = seg['text'].lower().strip()
                next_text = next_seg['text'].lower().strip()

                # Skip if next segment contains or starts with this text
                if next_text.startswith(current_text) or current_text in next_text:
                    i += 1
                    continue

            stage0.append(seg)
            i += 1

        if len(stage0) <= 1:
            return stage0

        # First pass: remove exact consecutive duplicates
        stage1 = []
        prev_text = None
        for seg in stage0:
            if seg['text'] != prev_text:
                stage1.append(seg)
                prev_text = seg['text']

        if len(stage1) <= 1:
            return stage1

        # Second pass: remove segments that are substrings of adjacent segments
        # (handles the rolling caption overlap)
        stage2 = []
        i = 0
        while i < len(stage1):
            current = stage1[i]
            current_text = current['text'].lower().strip()

            # Check if current is a prefix of next segment
            skip_current = False
            if i + 1 < len(stage1):
                next_seg = stage1[i + 1]
                next_text = next_seg['text'].lower().strip()
                # If current text is the start of next text, skip current (keep longer)
                if next_text.startswith(current_text) and len(next_text) > len(current_text):
                    skip_current = True
                # Note: rolling overlap cases (where current ends flow into next) are handled
                # by pass 3 merging, not by skipping

            # Check if current is a suffix of previous segment
            if not skip_current and stage2:
                prev_text = stage2[-1]['text'].lower().strip()
                # If previous text ends with current text, skip current (it's a leftover fragment)
                if prev_text.endswith(current_text) and len(prev_text) > len(current_text):
                    skip_current = True
                # Check for rolling overlap from previous - current starts with end of previous
                # This means current is just a fragment, skip it
                elif len(current_text) < len(prev_text) and self._has_rolling_overlap(prev_text, current_text):
                    skip_current = True

            if not skip_current:
                stage2.append(current)

            i += 1

        # Third pass: merge segments with significant overlap
        result = []
        for seg in stage2:
            if not result:
                result.append(seg)
                continue

            prev = result[-1]
            overlap = self._find_text_overlap(prev['text'], seg['text'])

            if overlap and len(overlap) > 10:  # Significant overlap
                # Merge by extending previous segment
                merged_text = prev['text'] + seg['text'][len(overlap):]
                result[-1] = {
                    'start': prev['start'],
                    'end': seg['end'],
                    'text': merged_text
                }
            else:
                result.append(seg)

        return result

    def _has_rolling_overlap(self, text1: str, text2: str) -> bool:
        """
        Check if text2 starts with the end of text1 (rolling caption pattern).
        Returns True if there's significant overlap suggesting rolling captions.
        """
        # Look for overlap of at least 3 words
        words1 = text1.split()
        words2 = text2.split()

        if len(words1) < 2 or len(words2) < 2:
            return False

        # Check if text2 starts with the last 2-4 words of text1
        for overlap_size in range(min(4, len(words1)), 1, -1):
            end_of_text1 = ' '.join(words1[-overlap_size:])
            start_of_text2 = ' '.join(words2[:overlap_size])
            if end_of_text1.lower() == start_of_text2.lower():
                return True

        return False

    def _find_text_overlap(self, text1: str, text2: str) -> str:
        """
        Find the overlapping text where text1 ends and text2 begins.
        Returns the overlapping portion, or empty string if no significant overlap.
        """
        # Check progressively smaller suffixes of text1 against prefixes of text2
        min_overlap = 5  # Minimum characters to consider as overlap

        for i in range(len(text1) - min_overlap, -1, -1):
            suffix = text1[i:]
            if text2.lower().startswith(suffix.lower()):
                return suffix

        return ""
    
    def _time_to_seconds(self, time_str: str) -> float:
        """Convert HH:MM:SS.mmm to seconds"""
        parts = time_str.split(':')
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    
    def process_batch(self, videos: List[VideoInfo], batch_number: int = 1) -> CaptionBatch:
        """Process a batch of videos and create output JSON"""
        logger.info(f"Processing batch {batch_number} with {len(videos)} videos")
        
        video_captions = []
        mapping_applied = not self.mapper.is_empty()
        
        for i, video in enumerate(videos):
            logger.info(f"  [{i+1}/{len(videos)}] {video.title[:50]}...")
            
            caption_file = self.download_captions(video)
            if caption_file is None:
                logger.warning(f"    Skipping - no captions available")
                continue
            
            segments = self.parse_vtt(caption_file)
            if not segments:
                logger.warning(f"    Skipping - no segments parsed")
                continue
            
            # Build full text
            full_text = ' '.join(seg['text'] for seg in segments)
            
            # Apply terminology mapping if available
            if mapping_applied:
                full_text = self.mapper.apply_mappings(full_text)
                for seg in segments:
                    seg['text'] = self.mapper.apply_mappings(seg['text'])
            
            video_captions.append({
                'video_id': video.video_id,
                'title': video.title,
                'url': video.url,
                'upload_date': video.upload_date,
                'segments': segments,
                'full_text': full_text
            })

            # Register video in tracker
            self.tracker.register_video(
                video_id=video.video_id,
                title=video.title,
                url=video.url,
                upload_date=video.upload_date,
                caption_file=caption_file
            )

            logger.info(f"    Processed {len(segments)} segments")
        
        batch = CaptionBatch(
            batch_number=batch_number,
            batch_size=len(video_captions),
            created_at=datetime.now().isoformat(),
            mapping_applied=mapping_applied,
            mapping_file=str(MAPPING_FILE) if mapping_applied else None,
            videos=video_captions
        )
        
        return batch
    
    def save_batch(self, batch: CaptionBatch, output_file: Optional[Path] = None) -> Path:
        """Save batch to JSON file"""
        if output_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = self.output_dir / f"captions_batch_{batch.batch_number}_{timestamp}.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(asdict(batch), f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved batch to: {output_file}")
        return output_file


# ============================================================================
# CLI INTERFACE
# ============================================================================
def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Download YouTube captions in batches for spell checking",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download from a channel
  python caption_downloader.py --channel "https://www.youtube.com/@moonsensei"

  # Download from a playlist
  python caption_downloader.py --playlist "https://www.youtube.com/playlist?list=PLxxx"

  # Download specific videos
  python caption_downloader.py --video "https://www.youtube.com/watch?v=abc123" \\
                               --video "https://www.youtube.com/watch?v=def456"

  # Mix channels, playlists, and videos
  python caption_downloader.py --channel "https://www.youtube.com/@channel1" \\
                               --playlist "https://www.youtube.com/playlist?list=PLxxx" \\
                               --video "https://www.youtube.com/watch?v=abc123"

  # Read URLs from a file (one per line, # for comments)
  python caption_downloader.py --input urls.txt

  # Auto-detect URL types
  python caption_downloader.py --url "https://www.youtube.com/@moonsensei" \\
                               --url "https://www.youtube.com/watch?v=abc123"

Environment Variables (set in .env):
  TERMINOLOGY_MAPPING_FILE  - Path to terminology mapping JSON
  CACHE_DIR                 - Cache directory (default: .cache)
  BATCH_SIZE                - Default batch size (default: 8)
        """
    )

    # Multiple source options (not mutually exclusive)
    parser.add_argument('--channel', '-c', action='append', default=[],
                       help='YouTube channel URL (can specify multiple)')
    parser.add_argument('--playlist', '-p', action='append', default=[],
                       help='YouTube playlist URL (can specify multiple)')
    parser.add_argument('--video', '-v', action='append', default=[],
                       help='YouTube video URL (can specify multiple)')
    parser.add_argument('--url', '-u', action='append', default=[],
                       help='Any YouTube URL (auto-detect type, can specify multiple)')
    parser.add_argument('--input', '-i', type=Path,
                       help='Read URLs from file (one per line, # for comments)')

    parser.add_argument('--batch-size', '-b', type=int, default=None,
                       help=f'Videos per batch (default: all videos if batches=1, else {BATCH_SIZE})')
    parser.add_argument('--batches', '-n', type=int, default=1,
                       help='Number of batches to download (default: 1)')
    parser.add_argument('--max-per-source', type=int, default=100,
                       help='Max videos per channel/playlist (default: 100)')
    parser.add_argument('--output', '-o', help='Output file path (optional)')
    parser.add_argument('--as-playlist', action='store_true',
                       help='Treat video+list URLs as playlists (download all videos)')
    parser.add_argument('--debug', '-d', action='store_true',
                       help='Enable debug output')

    args = parser.parse_args()

    if args.debug:
        console_handler.setLevel(logging.DEBUG)

    # Collect all URLs
    all_urls = []

    # Add explicit channels
    all_urls.extend(args.channel)

    # Add explicit playlists
    all_urls.extend(args.playlist)

    # Add explicit videos
    all_urls.extend(args.video)

    # Add auto-detect URLs
    all_urls.extend(args.url)

    # Read from input file if specified
    if args.input:
        if not args.input.exists():
            print(f"❌ Input file not found: {args.input}")
            sys.exit(1)

        with open(args.input, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    all_urls.append(line)
        print(f"📄 Read {len(all_urls)} URLs from {args.input}")

    # Validate we have at least one source
    if not all_urls:
        print("❌ No URLs provided. Use --channel, --playlist, --video, --url, or --input")
        parser.print_help()
        sys.exit(1)

    # Initialize downloader
    downloader = CaptionDownloader()

    # Report mapping status
    if downloader.mapper.is_empty():
        print(f"\n📋 No terminology mappings loaded")
        print(f"   (Set TERMINOLOGY_MAPPING_FILE in .env to apply corrections)")
    else:
        print(f"\n✅ Loaded {len(downloader.mapper.mappings)} terminology mappings")
        print(f"   from: {MAPPING_FILE}")

    # Fetch videos from all sources
    print(f"\n🔍 Fetching videos from {len(all_urls)} source(s)...")

    try:
        videos = downloader.get_videos_from_urls(
            all_urls,
            args.max_per_source,
            force_playlist=args.as_playlist
        )
    except Exception as e:
        print(f"\n❌ Error fetching videos: {e}")
        sys.exit(1)

    if not videos:
        print("❌ No videos found")
        sys.exit(1)

    # Determine batch size
    # If batch-size not specified and batches=1, process all videos in one batch
    # Otherwise use specified batch-size or default from BATCH_SIZE env var
    if args.batch_size is None:
        if args.batches == 1:
            batch_size = len(videos)  # All videos in one batch
        else:
            batch_size = int(BATCH_SIZE)
    else:
        batch_size = args.batch_size

    # Calculate total videos needed
    total_videos = batch_size * args.batches
    videos = videos[:total_videos]

    print(f"📺 Found {len(videos)} unique videos")

    # Process in batches
    output_files = []
    total_batches = (len(videos) + batch_size - 1) // batch_size
    total_batches = min(total_batches, args.batches)

    for batch_num in range(1, total_batches + 1):
        start_idx = (batch_num - 1) * batch_size
        end_idx = start_idx + batch_size
        batch_videos = videos[start_idx:end_idx]

        if not batch_videos:
            break

        print(f"\n📦 Processing batch {batch_num}/{total_batches} ({len(batch_videos)} videos)...")

        batch = downloader.process_batch(batch_videos, batch_num)

        if args.output and total_batches == 1:
            output_file = Path(args.output)
        else:
            output_file = None

        saved_path = downloader.save_batch(batch, output_file)
        output_files.append(saved_path)

        print(f"   ✅ Saved: {saved_path}")
        print(f"   📊 {batch.batch_size} videos processed")

    # Summary
    print(f"\n{'='*60}")
    print("📋 SUMMARY")
    print(f"{'='*60}")
    print(f"Total batches: {len(output_files)}")
    print(f"Mapping applied: {'Yes' if not downloader.mapper.is_empty() else 'No'}")
    print(f"\nOutput files:")
    for f in output_files:
        print(f"  📄 {f}")
    print(f"\n💡 Edit the 'full_text' fields to correct captions, then use")
    print(f"   caption_diff_mapper.py to generate terminology mappings")


if __name__ == "__main__":
    main()
