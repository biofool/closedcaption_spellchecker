"""Tests for caption watermark functionality"""

import pytest
import json
from datetime import datetime
from caption_watermark import (
    WatermarkConfig,
    generate_watermark_text,
    add_watermark_segment,
    add_watermark_to_json,
    remove_watermark_segment
)


class TestGenerateWatermarkText:
    def test_default_format(self, fixed_timestamp):
        text = generate_watermark_text(timestamp=fixed_timestamp)
        assert text == "Closed Captions Updated on 2025-01-15-14"

    def test_custom_format(self, fixed_timestamp):
        config = WatermarkConfig(format="Updated: {timestamp}")
        text = generate_watermark_text(config, fixed_timestamp)
        assert text == "Updated: 2025-01-15-14"

    def test_custom_timestamp_format(self, fixed_timestamp):
        config = WatermarkConfig(timestamp_format="%Y-%m-%d")
        text = generate_watermark_text(config, fixed_timestamp)
        assert "2025-01-15" in text

    def test_uses_current_time_when_none(self):
        text = generate_watermark_text()
        # Should contain today's date
        today = datetime.now().strftime("%Y-%m-%d")
        assert today in text


class TestAddWatermarkSegment:
    def test_watermark_added_at_end(self, sample_segments, fixed_timestamp):
        result = add_watermark_segment(sample_segments, timestamp=fixed_timestamp)

        assert len(result) == len(sample_segments) + 1
        last = result[-1]
        assert "Closed Captions Updated on" in last['text']

    def test_watermark_timing(self, sample_segments):
        config = WatermarkConfig(gap_seconds=2.0, duration_seconds=3.0)
        result = add_watermark_segment(sample_segments, config)

        last_original_end = sample_segments[-1]['end']  # 8.0
        watermark = result[-1]

        assert watermark['start'] == last_original_end + 2.0  # 10.0
        assert watermark['end'] == watermark['start'] + 3.0   # 13.0

    def test_empty_segments(self, fixed_timestamp):
        result = add_watermark_segment([], timestamp=fixed_timestamp)

        assert len(result) == 1
        assert result[0]['start'] == 0.0

    def test_original_not_modified(self, sample_segments):
        original_len = len(sample_segments)
        add_watermark_segment(sample_segments)

        assert len(sample_segments) == original_len  # Not mutated

    def test_watermark_has_correct_keys(self, sample_segments, fixed_timestamp):
        result = add_watermark_segment(sample_segments, timestamp=fixed_timestamp)
        watermark = result[-1]

        assert 'start' in watermark
        assert 'end' in watermark
        assert 'text' in watermark
        assert isinstance(watermark['start'], float)
        assert isinstance(watermark['end'], float)


class TestAddWatermarkToJson:
    def test_json_modification(self, sample_batch, fixed_timestamp, tmp_path):
        output_path = tmp_path / "output.json"
        add_watermark_to_json(sample_batch, output_path, timestamp=fixed_timestamp)

        with open(output_path) as f:
            data = json.load(f)

        video = data['videos'][0]
        segments = video['segments']

        # Check watermark added
        assert "Closed Captions Updated on" in segments[-1]['text']

        # Check full_text updated
        assert "Closed Captions Updated on" in video['full_text']

    def test_in_place_modification(self, sample_batch, fixed_timestamp):
        # Modify in place
        add_watermark_to_json(sample_batch, timestamp=fixed_timestamp)

        with open(sample_batch) as f:
            data = json.load(f)

        video = data['videos'][0]
        assert "Closed Captions Updated on" in video['segments'][-1]['text']


class TestRemoveWatermarkSegment:
    def test_removes_watermark(self, sample_segments, fixed_timestamp):
        with_watermark = add_watermark_segment(sample_segments, timestamp=fixed_timestamp)
        without = remove_watermark_segment(with_watermark)

        assert len(without) == len(sample_segments)
        assert "Closed Captions Updated" not in without[-1]['text']

    def test_no_watermark_present(self, sample_segments):
        result = remove_watermark_segment(sample_segments)
        assert result == sample_segments

    def test_empty_list(self):
        result = remove_watermark_segment([])
        assert result == []
