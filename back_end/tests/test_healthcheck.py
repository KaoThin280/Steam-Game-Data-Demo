import io
from unittest.mock import patch

import pytest

from app.healthcheck import check_health


@pytest.mark.parametrize('payload,expected', [
    (b'{"status":"healthy"}', True),
    (b'{"status":"degraded"}', False),
    (b'{}', False),
    (b'[]', False),
    (b'not-json', False),
])
def test_probe_validates_body_not_only_http_status(payload, expected):
    response = io.BytesIO(payload)
    response.status = 200
    with patch('app.healthcheck.urlopen', return_value=response):
        assert check_health('http://localhost/health') is expected


def test_unreachable_dependency_fails_probe():
    with patch('app.healthcheck.urlopen', side_effect=OSError('timeout')):
        assert not check_health('http://localhost/health')
