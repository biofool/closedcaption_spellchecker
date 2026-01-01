"""Tests for URL type detection"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from caption_downloader import CaptionDownloader


class TestUrlTypeDetection:
    """Test URL type auto-detection"""

    def test_channel_with_at_symbol(self):
        """Test channel URL with @ handle"""
        url = "https://www.youtube.com/@moonsensei"
        assert CaptionDownloader.detect_url_type(url) == 'channel'

    def test_channel_with_at_and_videos(self):
        """Test channel URL with @ handle and /videos"""
        url = "https://www.youtube.com/@moonsensei/videos"
        assert CaptionDownloader.detect_url_type(url) == 'channel'

    def test_channel_with_channel_id(self):
        """Test channel URL with channel ID"""
        url = "https://www.youtube.com/channel/UCxxxxxxxxxxxxx"
        assert CaptionDownloader.detect_url_type(url) == 'channel'

    def test_channel_with_c_format(self):
        """Test channel URL with /c/ format"""
        url = "https://www.youtube.com/c/SomeChannel"
        assert CaptionDownloader.detect_url_type(url) == 'channel'

    def test_channel_with_user_format(self):
        """Test channel URL with /user/ format"""
        url = "https://www.youtube.com/user/SomeUser"
        assert CaptionDownloader.detect_url_type(url) == 'channel'

    def test_playlist_url(self):
        """Test standard playlist URL"""
        url = "https://www.youtube.com/playlist?list=PLxxxxxxxx"
        assert CaptionDownloader.detect_url_type(url) == 'playlist'

    def test_playlist_with_list_param(self):
        """Test URL with only list parameter"""
        url = "https://www.youtube.com/watch?list=PLxxxxxxxx"
        assert CaptionDownloader.detect_url_type(url) == 'playlist'

    def test_studio_playlist_url(self):
        """Test YouTube Studio playlist URL"""
        url = "https://studio.youtube.com/playlist/PLxxxxxxxx/videos"
        assert CaptionDownloader.detect_url_type(url) == 'playlist'

    def test_video_watch_url(self):
        """Test standard video watch URL"""
        url = "https://www.youtube.com/watch?v=abc123xyz45"
        assert CaptionDownloader.detect_url_type(url) == 'video'

    def test_video_short_url(self):
        """Test youtu.be short URL"""
        url = "https://youtu.be/abc123xyz45"
        assert CaptionDownloader.detect_url_type(url) == 'video'

    def test_video_shorts_url(self):
        """Test YouTube Shorts URL"""
        url = "https://www.youtube.com/shorts/abc123xyz45"
        assert CaptionDownloader.detect_url_type(url) == 'video'

    def test_video_with_playlist_context(self):
        """Test video URL that includes playlist context (treat as video)"""
        url = "https://www.youtube.com/watch?v=abc123xyz45&list=PLxxxxxxxx"
        assert CaptionDownloader.detect_url_type(url) == 'video'

    def test_unknown_url(self):
        """Test non-YouTube URL"""
        url = "https://example.com/video"
        assert CaptionDownloader.detect_url_type(url) == 'unknown'

    def test_whitespace_handling(self):
        """Test URL with leading/trailing whitespace"""
        url = "  https://www.youtube.com/watch?v=abc123xyz45  "
        assert CaptionDownloader.detect_url_type(url) == 'video'
