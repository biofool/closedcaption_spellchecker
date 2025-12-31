"""
Round-trip test: Download -> Upload -> Download -> Verify

This test requires:
1. Valid YouTube API credentials (service account)
2. A test video the service account has access to
3. Network access

Run with: pytest tests/test_round_trip.py -v --run-integration
"""

import pytest
import os
import json
from pathlib import Path

# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture
def test_video_id():
    """
    Video ID for testing - should be a video the service account owns
    Set via environment variable or skip
    """
    video_id = os.getenv('TEST_VIDEO_ID')
    if not video_id:
        pytest.skip("TEST_VIDEO_ID not set - skipping integration test")
    return video_id


@pytest.fixture
def has_credentials():
    """Check if credentials are available"""
    has_file = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE')
    has_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
    if not (has_file or has_json):
        pytest.skip("No Google credentials configured - skipping integration test")
    return True


class TestRoundTrip:
    """
    Round-trip test verifying:
    1. Download original captions
    2. Upload unchanged
    3. Download again
    4. All three versions match
    """

    def test_caption_round_trip(self, test_video_id, has_credentials, tmp_path):
        """Test that captions survive a round-trip upload/download cycle"""
        from caption_downloader import CaptionDownloader, VideoInfo
        from caption_uploader import CaptionUploader
        from vtt_formatter import segments_to_vtt

        downloader = CaptionDownloader()
        uploader = CaptionUploader()

        # Step 1: Download original captions
        video = VideoInfo(
            video_id=test_video_id,
            title="Test",
            url=f"https://www.youtube.com/watch?v={test_video_id}",
            duration=0
        )

        caption_file = downloader.download_captions(video)
        assert caption_file is not None, "Failed to download original captions"

        original_segments = downloader.parse_vtt(caption_file)
        assert len(original_segments) > 0, "No segments parsed"

        original_vtt = segments_to_vtt(original_segments)

        # Step 2: Upload unchanged captions
        result = uploader.upload_caption(
            test_video_id,
            original_segments,
            language='en',
            name='English (Test)',
            replace_existing=True
        )
        assert result.success, f"Upload failed: {result.error_message}"

        # Step 3: Download again (clear cache first)
        if caption_file.exists():
            caption_file.unlink()

        caption_file_2 = downloader.download_captions(video)
        assert caption_file_2 is not None, "Failed to download after upload"

        downloaded_segments = downloader.parse_vtt(caption_file_2)
        downloaded_vtt = segments_to_vtt(downloaded_segments)

        # Step 4: Verify all match
        assert len(downloaded_segments) == len(original_segments), \
            f"Segment count mismatch: {len(downloaded_segments)} vs {len(original_segments)}"

        # Compare segment by segment
        for i, (orig, down) in enumerate(zip(original_segments, downloaded_segments)):
            assert orig['text'] == down['text'], \
                f"Text mismatch at segment {i}: '{orig['text']}' vs '{down['text']}'"

            # Allow small timing differences due to format conversion
            assert abs(orig['start'] - down['start']) < 0.1, \
                f"Start time mismatch at segment {i}"
            assert abs(orig['end'] - down['end']) < 0.1, \
                f"End time mismatch at segment {i}"

    def test_watermark_preservation(self, test_video_id, has_credentials, fixed_timestamp, tmp_path):
        """Test that watermark survives round-trip"""
        from caption_downloader import CaptionDownloader, VideoInfo
        from caption_uploader import CaptionUploader
        from caption_watermark import add_watermark_segment

        downloader = CaptionDownloader()
        uploader = CaptionUploader()

        video = VideoInfo(
            video_id=test_video_id,
            title="Test",
            url=f"https://www.youtube.com/watch?v={test_video_id}",
            duration=0
        )

        # Download and add watermark
        caption_file = downloader.download_captions(video)
        original_segments = downloader.parse_vtt(caption_file)
        watermarked = add_watermark_segment(original_segments, timestamp=fixed_timestamp)

        # Upload with watermark
        result = uploader.upload_caption(test_video_id, watermarked)
        assert result.success, f"Upload failed: {result.error_message}"

        # Download and verify watermark present
        if caption_file.exists():
            caption_file.unlink()

        caption_file_2 = downloader.download_captions(video)
        downloaded = downloader.parse_vtt(caption_file_2)

        # Last segment should be watermark
        assert "Closed Captions Updated on" in downloaded[-1]['text'], \
            "Watermark not found in downloaded captions"


class TestWatermarkTimestamp:
    """Test timestamp watermark functionality (no network required)"""

    def test_add_timestamp_to_single_file(self, sample_batch, fixed_timestamp, tmp_path):
        """Test adding timestamp to a single CC file"""
        from caption_watermark import add_watermark_to_json

        output_path = tmp_path / "watermarked.json"
        add_watermark_to_json(sample_batch, output_path, timestamp=fixed_timestamp)

        with open(output_path) as f:
            data = json.load(f)

        video = data['videos'][0]
        last_segment = video['segments'][-1]

        # Verify timestamp format: YYYY-MM-DD-HH
        expected = "Closed Captions Updated on 2025-01-15-14"
        assert last_segment['text'] == expected

    def test_timestamp_at_end_of_captions(self, sample_batch, fixed_timestamp, tmp_path):
        """Verify timestamp is placed at the end"""
        from caption_watermark import add_watermark_to_json

        output_path = tmp_path / "watermarked.json"
        add_watermark_to_json(sample_batch, output_path, timestamp=fixed_timestamp)

        with open(output_path) as f:
            data = json.load(f)

        video = data['videos'][0]
        segments = video['segments']

        # Original had 3 segments, now should have 4
        assert len(segments) == 4

        # Last one should be the watermark
        assert "Closed Captions Updated on" in segments[-1]['text']

        # Watermark should start after previous segment ends
        prev_end = segments[-2]['end']
        watermark_start = segments[-1]['start']
        assert watermark_start > prev_end
