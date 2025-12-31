#!/usr/bin/env python3
"""
Spellcheck Tracker - Track spell-check status and backup original captions
"""

import os
import json
import shutil
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass, field, asdict
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

# Configuration
REPO_ROOT = Path(__file__).parent
STATUS_FILE = REPO_ROOT / "spellcheck_status.json"
ORIGINALS_DIR = REPO_ROOT / "originals"


@dataclass
class VideoStatus:
    """Status information for a single video"""
    video_id: str
    title: str
    url: str
    original_caption_path: str
    spell_checked: bool = False
    spell_check_date: Optional[str] = None
    last_uploaded_date: Optional[str] = None
    added_date: str = field(default_factory=lambda: datetime.now().isoformat())
    upload_date: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict) -> 'VideoStatus':
        """Create VideoStatus from dictionary"""
        return cls(
            video_id=data['video_id'],
            title=data['title'],
            url=data['url'],
            original_caption_path=data['original_caption_path'],
            spell_checked=data.get('spell_checked', False),
            spell_check_date=data.get('spell_check_date'),
            last_uploaded_date=data.get('last_uploaded_date'),
            added_date=data.get('added_date', datetime.now().isoformat()),
            upload_date=data.get('upload_date')
        )


class SpellcheckTracker:
    """
    Manages spellcheck status tracking and original caption storage.

    Responsibilities:
    - Load/save spellcheck_status.json
    - Register new videos
    - Update spell-check status
    - Update upload status
    - Backup original captions to originals/ directory
    """

    def __init__(self, repo_root: Optional[Path] = None):
        """Initialize tracker with optional repo root path"""
        self.repo_root = Path(repo_root) if repo_root else REPO_ROOT
        self.status_file = self.repo_root / "spellcheck_status.json"
        self.originals_dir = self.repo_root / "originals"
        self._videos: Dict[str, VideoStatus] = {}
        self._load_status()

    def _load_status(self) -> None:
        """Load status from JSON file"""
        if not self.status_file.exists():
            self._videos = {}
            return

        try:
            with open(self.status_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            videos_data = data.get('videos', {})
            self._videos = {
                vid: VideoStatus.from_dict(vdata)
                for vid, vdata in videos_data.items()
            }
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Warning: Could not load status file: {e}")
            self._videos = {}

    def save_status(self) -> None:
        """Save status to JSON file"""
        data = {
            'version': '1.0',
            'updated_at': datetime.now().isoformat(),
            'video_count': len(self._videos),
            'videos': {
                vid: asdict(status)
                for vid, status in self._videos.items()
            }
        }

        with open(self.status_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def backup_original(self, video_id: str, caption_file: Path) -> Optional[Path]:
        """
        Copy caption file to originals directory.

        Returns path to backed up file.
        Skips if already exists (original should never be overwritten).
        """
        if not caption_file.exists():
            return None

        # Create originals directory
        self.originals_dir.mkdir(parents=True, exist_ok=True)

        # Determine extension
        ext = caption_file.suffix or '.vtt'
        backup_path = self.originals_dir / f"{video_id}{ext}"

        # Don't overwrite existing backup
        if backup_path.exists():
            return backup_path

        shutil.copy2(caption_file, backup_path)
        return backup_path

    def register_video(
        self,
        video_id: str,
        title: str,
        url: str,
        upload_date: Optional[str],
        caption_file: Optional[Path] = None
    ) -> VideoStatus:
        """
        Register a new video and optionally backup its original caption.

        - If caption_file provided, copies to originals/{video_id}.vtt
        - Creates VideoStatus entry
        - Saves status file
        """
        # Check if already registered
        if video_id in self._videos:
            return self._videos[video_id]

        # Backup original if provided
        original_path = ""
        if caption_file and caption_file.exists():
            backup = self.backup_original(video_id, caption_file)
            if backup:
                original_path = str(backup.relative_to(self.repo_root))

        # Create status entry
        status = VideoStatus(
            video_id=video_id,
            title=title,
            url=url,
            original_caption_path=original_path,
            upload_date=upload_date
        )

        self._videos[video_id] = status
        self.save_status()
        return status

    def mark_spell_checked(self, video_id: str) -> bool:
        """Mark a video as spell-checked with current timestamp"""
        if video_id not in self._videos:
            return False

        self._videos[video_id].spell_checked = True
        self._videos[video_id].spell_check_date = datetime.now().isoformat()
        self.save_status()
        return True

    def mark_uploaded(self, video_id: str) -> bool:
        """Update last_uploaded_date to current timestamp"""
        if video_id not in self._videos:
            return False

        self._videos[video_id].last_uploaded_date = datetime.now().isoformat()
        self.save_status()
        return True

    def get_video(self, video_id: str) -> Optional[VideoStatus]:
        """Get status for a specific video"""
        return self._videos.get(video_id)

    def get_all_videos(self) -> List[VideoStatus]:
        """Get all tracked videos as a list"""
        return list(self._videos.values())

    def filter_videos(
        self,
        spell_checked: Optional[bool] = None,
        checked_before: Optional[datetime] = None,
        checked_after: Optional[datetime] = None
    ) -> List[VideoStatus]:
        """Filter videos by criteria"""
        results = []

        for status in self._videos.values():
            # Filter by spell-check status
            if spell_checked is not None:
                if status.spell_checked != spell_checked:
                    continue

            # Filter by date
            if status.spell_check_date:
                check_date = datetime.fromisoformat(status.spell_check_date)

                if checked_before and check_date >= checked_before:
                    continue

                if checked_after and check_date <= checked_after:
                    continue
            elif checked_before or checked_after:
                # If filtering by date but video has no check date, skip it
                # unless we're looking for unchecked videos
                if spell_checked is not False:
                    continue

            results.append(status)

        return results

    def is_registered(self, video_id: str) -> bool:
        """Check if a video is already registered"""
        return video_id in self._videos

    def get_original_caption_path(self, video_id: str) -> Optional[Path]:
        """Get path to original caption file for a video"""
        status = self._videos.get(video_id)
        if not status or not status.original_caption_path:
            return None

        path = self.repo_root / status.original_caption_path
        return path if path.exists() else None

    def get_stats(self) -> Dict:
        """Get summary statistics"""
        total = len(self._videos)
        checked = sum(1 for v in self._videos.values() if v.spell_checked)
        uploaded = sum(1 for v in self._videos.values() if v.last_uploaded_date)

        return {
            'total': total,
            'spell_checked': checked,
            'not_checked': total - checked,
            'uploaded': uploaded
        }
