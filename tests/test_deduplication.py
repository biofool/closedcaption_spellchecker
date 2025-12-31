"""Tests for rolling caption deduplication"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from caption_downloader import CaptionDownloader


@pytest.fixture
def downloader():
    """Create downloader instance"""
    return CaptionDownloader()


class TestRollingCaptionDeduplication:
    """Test the rolling caption deduplication algorithm"""

    def test_exact_duplicates_removed(self, downloader):
        """Test that exact consecutive duplicates are removed"""
        segments = [
            {'start': 0.0, 'end': 2.0, 'text': 'Hello world'},
            {'start': 2.0, 'end': 4.0, 'text': 'Hello world'},
            {'start': 4.0, 'end': 6.0, 'text': 'Goodbye'},
        ]

        result = downloader._deduplicate_rolling_captions(segments)

        assert len(result) == 2
        assert result[0]['text'] == 'Hello world'
        assert result[1]['text'] == 'Goodbye'

    def test_prefix_duplicates_removed(self, downloader):
        """Test that prefix duplicates are removed (rolling caption pattern)"""
        segments = [
            {'start': 0.0, 'end': 2.0, 'text': 'Okay. So, Shane,'},
            {'start': 2.0, 'end': 4.0, 'text': 'Okay. So, Shane, um, push on me a little bit.'},
            {'start': 4.0, 'end': 6.0, 'text': 'um, push on me a little bit.'},
        ]

        result = downloader._deduplicate_rolling_captions(segments)

        # Should keep only the complete middle segment
        assert len(result) == 1
        assert 'Okay. So, Shane, um, push on me a little bit.' in result[0]['text']

    def test_suffix_duplicates_removed(self, downloader):
        """Test that suffix duplicates are removed"""
        segments = [
            {'start': 0.0, 'end': 2.0, 'text': 'This is the beginning of the sentence'},
            {'start': 2.0, 'end': 4.0, 'text': 'of the sentence'},
        ]

        result = downloader._deduplicate_rolling_captions(segments)

        assert len(result) == 1
        assert result[0]['text'] == 'This is the beginning of the sentence'

    def test_rolling_overlap_detected(self, downloader):
        """Test detection of rolling caption overlap"""
        # These have word-level overlap at the boundary
        text1 = "welcome to the dojo today"
        text2 = "the dojo today we practice"

        assert downloader._has_rolling_overlap(text1, text2) is True

    def test_no_overlap_detected(self, downloader):
        """Test that unrelated segments are not flagged as overlapping"""
        text1 = "welcome to the dojo"
        text2 = "now let us begin"

        assert downloader._has_rolling_overlap(text1, text2) is False

    def test_find_text_overlap(self, downloader):
        """Test finding overlapping text between segments"""
        text1 = "This is a test sentence"
        text2 = "test sentence that continues"

        overlap = downloader._find_text_overlap(text1, text2)

        assert overlap == "test sentence"

    def test_no_text_overlap(self, downloader):
        """Test when there's no text overlap"""
        text1 = "First sentence"
        text2 = "Unrelated text"

        overlap = downloader._find_text_overlap(text1, text2)

        assert overlap == ""

    def test_merge_overlapping_segments(self, downloader):
        """Test that overlapping segments are merged correctly"""
        segments = [
            {'start': 0.0, 'end': 3.0, 'text': 'Welcome to the dojo today we will'},
            {'start': 2.5, 'end': 5.0, 'text': 'today we will practice irimi tenkan'},
        ]

        result = downloader._deduplicate_rolling_captions(segments)

        # Should merge into one segment
        assert len(result) == 1
        assert 'Welcome to the dojo' in result[0]['text']
        assert 'practice irimi tenkan' in result[0]['text']

    def test_empty_segments(self, downloader):
        """Test handling of empty segment list"""
        result = downloader._deduplicate_rolling_captions([])
        assert result == []

    def test_single_segment(self, downloader):
        """Test handling of single segment"""
        segments = [{'start': 0.0, 'end': 2.0, 'text': 'Hello'}]

        result = downloader._deduplicate_rolling_captions(segments)

        assert len(result) == 1
        assert result[0]['text'] == 'Hello'

    def test_preserves_unique_segments(self, downloader):
        """Test that unique non-overlapping segments are preserved"""
        segments = [
            {'start': 0.0, 'end': 2.0, 'text': 'First unique sentence.'},
            {'start': 2.0, 'end': 4.0, 'text': 'Second unique sentence.'},
            {'start': 4.0, 'end': 6.0, 'text': 'Third unique sentence.'},
        ]

        result = downloader._deduplicate_rolling_captions(segments)

        assert len(result) == 3

    def test_complex_rolling_pattern(self, downloader):
        """Test a more complex rolling caption pattern"""
        segments = [
            {'start': 0.0, 'end': 2.0, 'text': 'So what I want you to'},
            {'start': 1.5, 'end': 3.5, 'text': 'So what I want you to do is push on me'},
            {'start': 3.0, 'end': 5.0, 'text': 'do is push on me right here'},
            {'start': 4.5, 'end': 6.5, 'text': 'right here on my chest'},
        ]

        result = downloader._deduplicate_rolling_captions(segments)

        # Should consolidate into fewer, cleaner segments
        assert len(result) < len(segments)
        # The final result should contain all the unique words
        full_text = ' '.join(seg['text'] for seg in result)
        assert 'what I want you to' in full_text
        assert 'push on me' in full_text
