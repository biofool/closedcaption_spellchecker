#!/usr/bin/env python3
"""
Caption Uploader - Upload captions to YouTube via Data API
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

# Configuration
CACHE_DIR = Path(os.getenv("CACHE_DIR", ".cache"))
LOG_DIR = CACHE_DIR / "logs"
TEMP_DIR = CACHE_DIR / "temp"

SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']

# Create directories
for directory in [CACHE_DIR, LOG_DIR, TEMP_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Logging
LOG_FILE = LOG_DIR / f"uploader_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logger = logging.getLogger("CaptionUploader")
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

# Import Google libraries (may not be installed)
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False
    logger.warning("Google API libraries not installed. Run: pip install google-api-python-client google-auth")

from vtt_formatter import segments_to_vtt, save_vtt


@dataclass
class UploadResult:
    """Result of a caption upload operation"""
    video_id: str
    caption_id: str
    success: bool
    error_message: Optional[str] = None


class CaptionUploader:
    """Upload captions to YouTube using the Data API"""

    def __init__(self):
        if not GOOGLE_API_AVAILABLE:
            raise ImportError(
                "Google API libraries not installed. "
                "Run: pip install google-api-python-client google-auth"
            )
        self.youtube = self._get_youtube_service()
        self.temp_dir = TEMP_DIR
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def _get_credentials(self):
        """Load service account credentials"""
        # Try JSON content first (for CI/CD)
        json_content = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
        if json_content:
            info = json.loads(json_content)
            return service_account.Credentials.from_service_account_info(
                info, scopes=SCOPES
            )

        # Try file path
        file_path = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE')
        if file_path and Path(file_path).exists():
            return service_account.Credentials.from_service_account_file(
                file_path, scopes=SCOPES
            )

        raise ValueError(
            "No service account credentials found. Set "
            "GOOGLE_SERVICE_ACCOUNT_FILE or GOOGLE_SERVICE_ACCOUNT_JSON in .env"
        )

    def _get_youtube_service(self):
        """Build authenticated YouTube API service"""
        credentials = self._get_credentials()
        return build('youtube', 'v3', credentials=credentials)

    def list_captions(self, video_id: str) -> List[Dict]:
        """List all caption tracks for a video"""
        request = self.youtube.captions().list(
            part="snippet",
            videoId=video_id
        )
        response = request.execute()
        return response.get('items', [])

    def get_caption_id(self, video_id: str, language: str = 'en') -> Optional[str]:
        """Get the caption ID for a specific language"""
        captions = self.list_captions(video_id)
        for caption in captions:
            if caption['snippet']['language'] == language:
                return caption['id']
        return None

    def delete_caption(self, caption_id: str) -> bool:
        """Delete a caption track"""
        try:
            self.youtube.captions().delete(id=caption_id).execute()
            logger.info(f"Deleted caption: {caption_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete caption {caption_id}: {e}")
            return False

    def download_caption(self, caption_id: str) -> Optional[str]:
        """Download caption content by ID"""
        try:
            request = self.youtube.captions().download(
                id=caption_id,
                tfmt='vtt'
            )
            response = request.execute()
            return response.decode('utf-8') if isinstance(response, bytes) else response
        except Exception as e:
            logger.error(f"Failed to download caption {caption_id}: {e}")
            return None

    def upload_caption(
        self,
        video_id: str,
        segments: List[Dict],
        language: str = 'en',
        name: str = 'English',
        replace_existing: bool = True
    ) -> UploadResult:
        """
        Upload captions to a YouTube video

        Args:
            video_id: YouTube video ID
            segments: List of caption segments with start, end, text
            language: Caption language code (default: 'en')
            name: Display name for the caption track
            replace_existing: If True, delete existing caption first

        Returns:
            UploadResult with success status and caption ID
        """
        try:
            # Delete existing caption if requested
            if replace_existing:
                existing_id = self.get_caption_id(video_id, language)
                if existing_id:
                    logger.info(f"Deleting existing caption: {existing_id}")
                    self.delete_caption(existing_id)

            # Create temporary VTT file
            vtt_path = self.temp_dir / f"{video_id}_{language}.vtt"
            save_vtt(segments, vtt_path)

            # Upload
            body = {
                'snippet': {
                    'videoId': video_id,
                    'language': language,
                    'name': name,
                    'isDraft': False
                }
            }

            media = MediaFileUpload(
                str(vtt_path),
                mimetype='text/vtt',
                resumable=True
            )

            request = self.youtube.captions().insert(
                part='snippet',
                body=body,
                media_body=media
            )

            response = request.execute()
            caption_id = response['id']

            logger.info(f"Uploaded caption {caption_id} to video {video_id}")

            # Clean up temp file
            vtt_path.unlink(missing_ok=True)

            return UploadResult(
                video_id=video_id,
                caption_id=caption_id,
                success=True
            )

        except Exception as e:
            logger.error(f"Upload failed for {video_id}: {e}")
            return UploadResult(
                video_id=video_id,
                caption_id='',
                success=False,
                error_message=str(e)
            )

    def upload_from_json(
        self,
        json_path: Path,
        video_id: Optional[str] = None
    ) -> List[UploadResult]:
        """
        Upload captions from a JSON batch file

        Args:
            json_path: Path to caption JSON file
            video_id: If provided, only upload for this video

        Returns:
            List of UploadResult for each video
        """
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        results = []
        videos = data.get('videos', [])

        for video in videos:
            vid = video['video_id']

            if video_id and vid != video_id:
                continue

            segments = video.get('segments', [])
            if not segments:
                logger.warning(f"No segments for video {vid}")
                continue

            result = self.upload_caption(vid, segments)
            results.append(result)

        return results


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Upload corrected captions to YouTube",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Upload all videos from a batch file
  python caption_uploader.py captions_batch_1.json

  # Upload only a specific video
  python caption_uploader.py captions_batch_1.json --video abc123xyz

  # Dry run to see what would be uploaded
  python caption_uploader.py captions_batch_1.json --dry-run

Environment Variables:
  GOOGLE_SERVICE_ACCOUNT_FILE  - Path to service account JSON key
  GOOGLE_SERVICE_ACCOUNT_JSON  - JSON content directly (for CI/CD)
        """
    )

    parser.add_argument('json_file', help='Caption JSON file to upload')
    parser.add_argument('--video', '-v', help='Upload only for specific video ID')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be uploaded without uploading')
    parser.add_argument('--debug', '-d', action='store_true',
                       help='Enable debug output')

    args = parser.parse_args()

    if args.debug:
        console_handler.setLevel(logging.DEBUG)

    json_path = Path(args.json_file)
    if not json_path.exists():
        print(f"Error: File not found: {json_path}")
        sys.exit(1)

    # Load and display info
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    videos = data.get('videos', [])
    if args.video:
        videos = [v for v in videos if v['video_id'] == args.video]

    print(f"\nCaption Upload")
    print(f"{'='*60}")
    print(f"File: {json_path}")
    print(f"Videos to upload: {len(videos)}")

    if args.dry_run:
        print(f"\n[DRY RUN] Would upload:")
        for video in videos:
            print(f"  - {video['video_id']}: {video['title'][:40]}...")
            print(f"    Segments: {len(video.get('segments', []))}")
        return

    try:
        uploader = CaptionUploader()
    except (ImportError, ValueError) as e:
        print(f"\nError: {e}")
        sys.exit(1)

    print(f"\nUploading...")
    results = uploader.upload_from_json(json_path, args.video)

    # Summary
    success_count = sum(1 for r in results if r.success)
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Successful: {success_count}/{len(results)}")

    for result in results:
        status = "OK" if result.success else "FAILED"
        print(f"  [{status}] {result.video_id}")
        if result.error_message:
            print(f"       Error: {result.error_message}")


if __name__ == "__main__":
    main()
