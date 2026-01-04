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

    def test_studio_playlist_with_channel(self):
        """Test YouTube Studio channel playlists URL"""
        url = "https://studio.youtube.com/channel/UCxxxxx/playlists"
        # This should be detected as channel since it contains /channel/
        assert CaptionDownloader.detect_url_type(url) == 'channel'

    def test_course_url_with_playnext(self):
        """Test YouTube course URL with playnext parameter"""
        url = "https://www.youtube.com/playlist?list=PLxxxxxxxx&playnext=1"
        assert CaptionDownloader.detect_url_type(url) == 'playlist'


class TestExtractPlaylistId:
    """Test playlist ID extraction from various URL formats"""

    def test_standard_playlist_url(self):
        """Test extracting from standard playlist URL"""
        url = "https://www.youtube.com/playlist?list=PLtest123abc"
        assert CaptionDownloader.extract_playlist_id(url) == 'PLtest123abc'

    def test_video_with_list_param(self):
        """Test extracting from video URL with list parameter"""
        url = "https://www.youtube.com/watch?v=abc123&list=PLcourse456"
        assert CaptionDownloader.extract_playlist_id(url) == 'PLcourse456'

    def test_studio_playlist_url(self):
        """Test extracting from YouTube Studio playlist URL"""
        url = "https://studio.youtube.com/playlist/PLstudio789/videos"
        assert CaptionDownloader.extract_playlist_id(url) == 'PLstudio789'

    def test_watch_list_only(self):
        """Test extracting from watch URL with only list param"""
        url = "https://www.youtube.com/watch?list=PLwatchlist"
        assert CaptionDownloader.extract_playlist_id(url) == 'PLwatchlist'

    def test_no_playlist(self):
        """Test URL without playlist returns None"""
        url = "https://www.youtube.com/watch?v=abc123"
        assert CaptionDownloader.extract_playlist_id(url) is None

    def test_channel_url(self):
        """Test channel URL returns None"""
        url = "https://www.youtube.com/@moonsensei"
        assert CaptionDownloader.extract_playlist_id(url) is None


class TestConvertToStandardUrl:
    """Test URL conversion to standard format"""

    def test_studio_playlist_conversion(self):
        """Test converting Studio playlist URL to standard format"""
        url = "https://studio.youtube.com/playlist/PLtest123/videos"
        result = CaptionDownloader.convert_to_standard_url(url)
        assert result == "https://www.youtube.com/playlist?list=PLtest123"

    def test_regular_url_unchanged(self):
        """Test regular URLs pass through unchanged"""
        url = "https://www.youtube.com/playlist?list=PLtest123"
        result = CaptionDownloader.convert_to_standard_url(url)
        assert result == url

    def test_video_url_unchanged(self):
        """Test video URLs pass through unchanged"""
        url = "https://www.youtube.com/watch?v=abc123"
        result = CaptionDownloader.convert_to_standard_url(url)
        assert result == url
