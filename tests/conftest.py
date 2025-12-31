"""Pytest fixtures for caption tests"""

import pytest
import json
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def pytest_addoption(parser):
    """Add custom command line options"""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests that require network/credentials"
    )


def pytest_configure(config):
    """Configure pytest markers"""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )


def pytest_collection_modifyitems(config, items):
    """Skip integration tests unless --run-integration is passed"""
    if config.getoption("--run-integration"):
        return

    skip_integration = pytest.mark.skip(reason="Need --run-integration option to run")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


@pytest.fixture
def sample_segments():
    """Sample caption segments for testing"""
    return [
        {'start': 0.0, 'end': 2.5, 'text': 'Welcome to the dojo'},
        {'start': 2.5, 'end': 5.0, 'text': 'Today we practice Aikido'},
        {'start': 5.0, 'end': 8.0, 'text': 'Let us begin with irimi tenkan'},
    ]


@pytest.fixture
def sample_batch(sample_segments, tmp_path):
    """Create a sample batch JSON file"""
    batch_data = {
        'batch_number': 1,
        'batch_size': 1,
        'created_at': datetime.now().isoformat(),
        'mapping_applied': False,
        'mapping_file': None,
        'videos': [{
            'video_id': 'test123',
            'title': 'Test Video',
            'url': 'https://www.youtube.com/watch?v=test123',
            'upload_date': '20250101',
            'segments': sample_segments,
            'full_text': ' '.join(seg['text'] for seg in sample_segments)
        }]
    }

    json_path = tmp_path / 'test_batch.json'
    json_path.write_text(json.dumps(batch_data, indent=2))
    return json_path


@pytest.fixture
def fixed_timestamp():
    """Fixed timestamp for deterministic tests"""
    return datetime(2025, 1, 15, 14, 0, 0)
