"""Tests for caption concatenator"""

import pytest
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from caption_concatenator import (
    load_batch_file,
    parse_upload_date,
    format_date_str,
    format_video_date,
    extract_date_from_title,
    get_video_date,
    fix_duplicate_words,
    concatenate_text
)


@pytest.fixture
def sample_batch_file(tmp_path):
    """Create a sample batch JSON file"""
    batch_data = {
        "batch_number": 1,
        "videos": [
            {
                "video_id": "abc123",
                "title": "First Video",
                "url": "https://youtube.com/watch?v=abc123",
                "upload_date": "20240115",
                "full_text": "This is the first video content."
            },
            {
                "video_id": "def456",
                "title": "Second Video",
                "url": "https://youtube.com/watch?v=def456",
                "upload_date": "20240110",
                "full_text": "This is the second video content."
            },
            {
                "video_id": "ghi789",
                "title": "Third Video",
                "url": "https://youtube.com/watch?v=ghi789",
                "upload_date": "20240120",
                "full_text": "This is the third video content."
            }
        ]
    }

    file_path = tmp_path / "test_batch.json"
    with open(file_path, 'w') as f:
        json.dump(batch_data, f)

    return file_path


class TestParseUploadDate:
    """Test upload date parsing"""

    def test_parse_yyyymmdd(self):
        """Test parsing YYYYMMDD format"""
        result = parse_upload_date("20240115")
        assert result == datetime(2024, 1, 15)

    def test_parse_iso_date(self):
        """Test parsing YYYY-MM-DD format"""
        result = parse_upload_date("2024-01-15")
        assert result == datetime(2024, 1, 15)

    def test_parse_none(self):
        """Test parsing None"""
        result = parse_upload_date(None)
        assert result is None

    def test_parse_empty_string(self):
        """Test parsing empty string"""
        result = parse_upload_date("")
        assert result is None


class TestFormatDate:
    """Test date formatting"""

    def test_format_yyyymmdd(self):
        """Test formatting YYYYMMDD date"""
        result = format_date_str("20240115")
        assert result == "2024-01-15"

    def test_format_none(self):
        """Test formatting None date"""
        result = format_date_str(None)
        assert result == "Unknown date"


class TestExtractDateFromTitle:
    """Test extracting dates from video titles"""

    def test_yyyy_mm_dd_dash(self):
        """Test YYYY-MM-DD format"""
        result = extract_date_from_title("Aikido Class 2024-01-15 Morning Session")
        assert result == datetime(2024, 1, 15)

    def test_yyyy_mm_dd_slash(self):
        """Test YYYY/MM/DD format"""
        result = extract_date_from_title("Class 2024/01/15")
        assert result == datetime(2024, 1, 15)

    def test_mm_dd_yyyy(self):
        """Test MM-DD-YYYY format"""
        result = extract_date_from_title("Class 01-15-2024")
        assert result == datetime(2024, 1, 15)

    def test_month_name_format(self):
        """Test 'Jan 15, 2024' format"""
        result = extract_date_from_title("Aikido Class Jan 15, 2024")
        assert result == datetime(2024, 1, 15)

    def test_full_month_name(self):
        """Test 'January 15, 2024' format"""
        result = extract_date_from_title("Aikido Class January 15, 2024")
        assert result == datetime(2024, 1, 15)

    def test_day_month_year(self):
        """Test '15 Jan 2024' format"""
        result = extract_date_from_title("Class 15 Jan 2024")
        assert result == datetime(2024, 1, 15)

    def test_no_date_in_title(self):
        """Test title without date"""
        result = extract_date_from_title("Aikido Introduction Video")
        assert result is None

    def test_empty_title(self):
        """Test empty title"""
        result = extract_date_from_title("")
        assert result is None


class TestGetVideoDate:
    """Test getting best date from video"""

    def test_prefers_upload_date(self):
        """Test that upload_date is preferred over title"""
        video = {
            'title': 'Class 2024-01-20',
            'upload_date': '20240115'
        }
        result = get_video_date(video)
        assert result == datetime(2024, 1, 15)

    def test_falls_back_to_title(self):
        """Test fallback to title when no upload_date"""
        video = {
            'title': 'Aikido Class 2024-01-15',
            'upload_date': None
        }
        result = get_video_date(video)
        assert result == datetime(2024, 1, 15)

    def test_no_date_available(self):
        """Test when no date is available"""
        video = {
            'title': 'Aikido Introduction',
            'upload_date': None
        }
        result = get_video_date(video)
        assert result is None


class TestFixDuplicateWords:
    """Test fixing duplicate consecutive words"""

    def test_single_duplicate(self):
        """Test single duplicate word pair"""
        result = fix_duplicate_words("the the quick brown fox")
        assert result == "the, quick brown fox"

    def test_triple_duplicate(self):
        """Test three consecutive duplicates: keep 1st, comma, keep 3rd"""
        result = fix_duplicate_words("I I I think so")
        assert result == "I, I think so"

    def test_quadruple_duplicate(self):
        """Test four consecutive duplicates"""
        result = fix_duplicate_words("go go go go now")
        assert result == "go, go, now"

    def test_multiple_duplicate_groups(self):
        """Test multiple groups of duplicates"""
        result = fix_duplicate_words("the the quick quick fox")
        assert result == "the, quick, fox"

    def test_no_duplicates(self):
        """Test text without duplicates"""
        result = fix_duplicate_words("the quick brown fox")
        assert result == "the quick brown fox"

    def test_case_insensitive(self):
        """Test case-insensitive duplicate detection"""
        result = fix_duplicate_words("The the quick")
        assert result == "The, quick"

    def test_empty_string(self):
        """Test empty string"""
        result = fix_duplicate_words("")
        assert result == ""

    def test_single_word(self):
        """Test single word"""
        result = fix_duplicate_words("hello")
        assert result == "hello"

    def test_preserves_punctuation(self):
        """Test that punctuation is preserved"""
        result = fix_duplicate_words("Hello. The the end.")
        assert "the," in result.lower() or "The," in result


class TestLoadBatchFile:
    """Test batch file loading"""

    def test_load_videos(self, sample_batch_file):
        """Test loading videos from batch file"""
        videos = load_batch_file(sample_batch_file)
        assert len(videos) == 3
        assert videos[0]['video_id'] == 'abc123'


class TestConcatenateText:
    """Test text concatenation"""

    def test_concatenate_sorted_by_date(self, sample_batch_file):
        """Test that videos are sorted by upload date (oldest first)"""
        result = concatenate_text([sample_batch_file], output_format='text')

        # Second video (20240110) should appear before First (20240115)
        pos_second = result.find("Second Video")
        pos_first = result.find("First Video")
        pos_third = result.find("Third Video")

        assert pos_second < pos_first < pos_third

    def test_concatenate_reverse_order(self, sample_batch_file):
        """Test reverse order (newest first)"""
        result = concatenate_text([sample_batch_file], output_format='text', reverse_order=True)

        # Third video (20240120) should appear first
        pos_third = result.find("Third Video")
        pos_first = result.find("First Video")
        pos_second = result.find("Second Video")

        assert pos_third < pos_first < pos_second

    def test_concatenate_includes_content(self, sample_batch_file):
        """Test that full text is included"""
        result = concatenate_text([sample_batch_file], output_format='text')

        assert "This is the first video content." in result
        assert "This is the second video content." in result
        assert "This is the third video content." in result

    def test_concatenate_markdown_format(self, sample_batch_file):
        """Test markdown output format"""
        result = concatenate_text([sample_batch_file], output_format='markdown')

        assert "# Combined Captions" in result
        assert "## First Video" in result
        assert "**Date:**" in result
        assert "**URL:**" in result

    def test_concatenate_no_metadata(self, sample_batch_file):
        """Test output without metadata"""
        result = concatenate_text(
            [sample_batch_file],
            output_format='text',
            include_metadata=False
        )

        # Should still have content but no video titles as headers
        assert "This is the first video content." in result
        # The title shouldn't appear as a header line
        lines = result.split('\n')
        header_lines = [l for l in lines if l.startswith('Video:')]
        assert len(header_lines) == 0
