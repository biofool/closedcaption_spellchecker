"""Tests for caption uploader"""

import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestCaptionUploaderUnit:
    """Unit tests with mocked YouTube API"""

    @pytest.fixture
    def mock_youtube_service(self):
        """Mock YouTube API service"""
        mock_service = MagicMock()

        # Mock captions().list()
        mock_service.captions().list().execute.return_value = {
            'items': [
                {'id': 'caption123', 'snippet': {'language': 'en'}}
            ]
        }

        # Mock captions().delete()
        mock_service.captions().delete().execute.return_value = {}

        # Mock captions().insert()
        mock_service.captions().insert().execute.return_value = {
            'id': 'new_caption_456'
        }

        return mock_service

    @pytest.fixture
    def mock_credentials(self):
        """Mock service account credentials"""
        with patch.dict('os.environ', {'GOOGLE_SERVICE_ACCOUNT_FILE': 'fake.json'}):
            with patch('caption_uploader.service_account.Credentials.from_service_account_file') as mock:
                mock.return_value = MagicMock()
                yield mock

    def test_upload_result_dataclass(self):
        """Test UploadResult dataclass"""
        from caption_uploader import UploadResult

        result = UploadResult(
            video_id='abc123',
            caption_id='cap456',
            success=True
        )
        assert result.video_id == 'abc123'
        assert result.success is True
        assert result.error_message is None

    def test_upload_result_with_error(self):
        """Test UploadResult with error"""
        from caption_uploader import UploadResult

        result = UploadResult(
            video_id='abc123',
            caption_id='',
            success=False,
            error_message='Permission denied'
        )
        assert result.success is False
        assert result.error_message == 'Permission denied'


class TestVttGeneration:
    """Test VTT generation for upload"""

    def test_segments_converted_to_vtt(self, sample_segments, tmp_path):
        from vtt_formatter import save_vtt

        vtt_path = tmp_path / "test.vtt"
        save_vtt(sample_segments, vtt_path)

        content = vtt_path.read_text()
        assert content.startswith("WEBVTT")
        assert "Welcome to the dojo" in content


class TestUploadFromJson:
    """Test loading and parsing JSON for upload"""

    def test_load_batch_json(self, sample_batch):
        with open(sample_batch, 'r') as f:
            data = json.load(f)

        assert 'videos' in data
        assert len(data['videos']) == 1
        assert data['videos'][0]['video_id'] == 'test123'

    def test_segments_extracted(self, sample_batch):
        with open(sample_batch, 'r') as f:
            data = json.load(f)

        video = data['videos'][0]
        segments = video['segments']

        assert len(segments) == 3
        assert all('start' in s and 'end' in s and 'text' in s for s in segments)
