"""Tests for spellcheck tracker"""

import pytest
import json
from pathlib import Path
from datetime import datetime, timedelta

from spellcheck_tracker import SpellcheckTracker, VideoStatus


@pytest.fixture
def tracker(tmp_path):
    """Create tracker with temp directory"""
    return SpellcheckTracker(repo_root=tmp_path)


@pytest.fixture
def sample_vtt(tmp_path):
    """Create a sample VTT file for testing"""
    vtt_content = "WEBVTT\n\n1\n00:00:00.000 --> 00:00:02.000\nHello world\n"
    vtt_path = tmp_path / "test.vtt"
    vtt_path.write_text(vtt_content)
    return vtt_path


class TestVideoStatus:
    def test_from_dict(self):
        """Test creating VideoStatus from dictionary"""
        data = {
            'video_id': 'test123',
            'title': 'Test Video',
            'url': 'https://youtube.com/watch?v=test123',
            'original_caption_path': 'originals/test123.vtt',
            'spell_checked': True,
            'spell_check_date': '2025-01-15T14:00:00',
            'last_uploaded_date': None,
            'added_date': '2025-01-15T10:00:00',
            'upload_date': '20250101'
        }

        status = VideoStatus.from_dict(data)

        assert status.video_id == 'test123'
        assert status.title == 'Test Video'
        assert status.spell_checked is True
        assert status.spell_check_date == '2025-01-15T14:00:00'


class TestSpellcheckTracker:
    def test_register_video(self, tracker, sample_vtt):
        """Test registering a new video"""
        status = tracker.register_video(
            video_id='test123',
            title='Test Video',
            url='https://youtube.com/watch?v=test123',
            upload_date='20250101',
            caption_file=sample_vtt
        )

        assert status.video_id == 'test123'
        assert status.title == 'Test Video'
        assert status.spell_checked is False
        assert tracker.is_registered('test123')

    def test_register_video_no_duplicate(self, tracker, sample_vtt):
        """Test that re-registering returns existing status"""
        status1 = tracker.register_video(
            video_id='test123',
            title='Test Video',
            url='https://youtube.com/watch?v=test123',
            upload_date='20250101',
            caption_file=sample_vtt
        )

        status2 = tracker.register_video(
            video_id='test123',
            title='Different Title',
            url='https://youtube.com/watch?v=test123',
            upload_date='20250101'
        )

        # Should return same status, not create new one
        assert status1.title == status2.title == 'Test Video'

    def test_backup_original(self, tracker, sample_vtt):
        """Test backing up original caption"""
        backup_path = tracker.backup_original('test123', sample_vtt)

        assert backup_path is not None
        assert backup_path.exists()
        assert backup_path.name == 'test123.vtt'
        assert backup_path.read_text() == sample_vtt.read_text()

    def test_backup_no_overwrite(self, tracker, sample_vtt, tmp_path):
        """Test that original is not overwritten on re-backup"""
        # First backup
        backup1 = tracker.backup_original('test123', sample_vtt)
        original_content = backup1.read_text()

        # Modify source file
        sample_vtt.write_text("WEBVTT\n\nModified content\n")

        # Second backup should not overwrite
        backup2 = tracker.backup_original('test123', sample_vtt)

        assert backup2.read_text() == original_content

    def test_mark_spell_checked(self, tracker, sample_vtt):
        """Test marking video as spell-checked"""
        tracker.register_video(
            video_id='test123',
            title='Test Video',
            url='https://youtube.com/watch?v=test123',
            upload_date='20250101',
            caption_file=sample_vtt
        )

        result = tracker.mark_spell_checked('test123')

        assert result is True
        status = tracker.get_video('test123')
        assert status.spell_checked is True
        assert status.spell_check_date is not None

    def test_mark_spell_checked_nonexistent(self, tracker):
        """Test marking nonexistent video"""
        result = tracker.mark_spell_checked('nonexistent')
        assert result is False

    def test_mark_uploaded(self, tracker, sample_vtt):
        """Test updating upload timestamp"""
        tracker.register_video(
            video_id='test123',
            title='Test Video',
            url='https://youtube.com/watch?v=test123',
            upload_date='20250101',
            caption_file=sample_vtt
        )

        result = tracker.mark_uploaded('test123')

        assert result is True
        status = tracker.get_video('test123')
        assert status.last_uploaded_date is not None

    def test_filter_by_spell_check_status(self, tracker, sample_vtt):
        """Test filtering by spell-check status"""
        # Register two videos
        tracker.register_video('vid1', 'Video 1', 'url1', '20250101', sample_vtt)
        tracker.register_video('vid2', 'Video 2', 'url2', '20250102')

        # Mark one as checked
        tracker.mark_spell_checked('vid1')

        # Filter checked
        checked = tracker.filter_videos(spell_checked=True)
        assert len(checked) == 1
        assert checked[0].video_id == 'vid1'

        # Filter unchecked
        unchecked = tracker.filter_videos(spell_checked=False)
        assert len(unchecked) == 1
        assert unchecked[0].video_id == 'vid2'

    def test_filter_by_date(self, tracker, sample_vtt):
        """Test filtering by date range"""
        # Register and check video
        tracker.register_video('vid1', 'Video 1', 'url1', '20250101', sample_vtt)
        tracker.mark_spell_checked('vid1')

        # Get the check date
        status = tracker.get_video('vid1')
        check_date = datetime.fromisoformat(status.spell_check_date)

        # Filter before (should exclude)
        before_results = tracker.filter_videos(
            checked_before=check_date - timedelta(hours=1)
        )
        assert len(before_results) == 0

        # Filter after (should include)
        after_results = tracker.filter_videos(
            checked_after=check_date - timedelta(hours=1)
        )
        assert len(after_results) == 1

    def test_persistence(self, tracker, sample_vtt, tmp_path):
        """Test that status survives reload"""
        tracker.register_video('test123', 'Test Video', 'url', '20250101', sample_vtt)
        tracker.mark_spell_checked('test123')

        # Create new tracker instance (simulates restart)
        tracker2 = SpellcheckTracker(repo_root=tmp_path)

        status = tracker2.get_video('test123')
        assert status is not None
        assert status.spell_checked is True

    def test_get_all_videos(self, tracker, sample_vtt):
        """Test getting all videos"""
        tracker.register_video('vid1', 'Video 1', 'url1', '20250101', sample_vtt)
        tracker.register_video('vid2', 'Video 2', 'url2', '20250102')

        all_videos = tracker.get_all_videos()

        assert len(all_videos) == 2

    def test_get_stats(self, tracker, sample_vtt):
        """Test getting statistics"""
        tracker.register_video('vid1', 'Video 1', 'url1', '20250101', sample_vtt)
        tracker.register_video('vid2', 'Video 2', 'url2', '20250102')
        tracker.mark_spell_checked('vid1')
        tracker.mark_uploaded('vid1')

        stats = tracker.get_stats()

        assert stats['total'] == 2
        assert stats['spell_checked'] == 1
        assert stats['not_checked'] == 1
        assert stats['uploaded'] == 1

    def test_get_original_caption_path(self, tracker, sample_vtt):
        """Test getting original caption path"""
        tracker.register_video('test123', 'Test', 'url', '20250101', sample_vtt)

        path = tracker.get_original_caption_path('test123')

        assert path is not None
        assert path.exists()

    def test_get_original_caption_path_nonexistent(self, tracker):
        """Test getting path for nonexistent video"""
        path = tracker.get_original_caption_path('nonexistent')
        assert path is None
