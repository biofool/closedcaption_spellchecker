"""Tests for VTT formatter"""

import pytest
from vtt_formatter import (
    seconds_to_vtt_timestamp,
    segments_to_vtt,
    save_vtt
)


class TestSecondsToTimestamp:
    def test_zero(self):
        assert seconds_to_vtt_timestamp(0.0) == "00:00:00.000"

    def test_seconds_only(self):
        assert seconds_to_vtt_timestamp(45.5) == "00:00:45.500"

    def test_minutes_and_seconds(self):
        assert seconds_to_vtt_timestamp(125.123) == "00:02:05.123"

    def test_hours(self):
        assert seconds_to_vtt_timestamp(3723.456) == "01:02:03.456"

    def test_milliseconds_precision(self):
        assert seconds_to_vtt_timestamp(1.001) == "00:00:01.001"
        assert seconds_to_vtt_timestamp(1.999) == "00:00:01.999"


class TestSegmentsToVtt:
    def test_basic_conversion(self, sample_segments):
        vtt = segments_to_vtt(sample_segments)

        assert vtt.startswith("WEBVTT")
        assert "00:00:00.000 --> 00:00:02.500" in vtt
        assert "Welcome to the dojo" in vtt

    def test_segment_numbering(self, sample_segments):
        vtt = segments_to_vtt(sample_segments)
        lines = vtt.split('\n')

        # Should have segment numbers
        assert '1' in lines
        assert '2' in lines
        assert '3' in lines

    def test_empty_segments(self):
        vtt = segments_to_vtt([])
        assert vtt == "WEBVTT\n"

    def test_all_segments_included(self, sample_segments):
        vtt = segments_to_vtt(sample_segments)

        for segment in sample_segments:
            assert segment['text'] in vtt


class TestSaveVtt:
    def test_file_creation(self, sample_segments, tmp_path):
        output_path = tmp_path / "test.vtt"
        result = save_vtt(sample_segments, output_path)

        assert result.exists()
        content = result.read_text()
        assert "WEBVTT" in content

    def test_file_encoding(self, tmp_path):
        segments = [{'start': 0.0, 'end': 1.0, 'text': 'Test with unicode: Aikidō 合気道'}]
        output_path = tmp_path / "unicode.vtt"

        result = save_vtt(segments, output_path)
        content = result.read_text(encoding='utf-8')

        assert 'Aikidō' in content
        assert '合気道' in content
