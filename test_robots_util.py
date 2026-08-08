"""Tests for robots.txt helpers (robots_util.py)."""
from __future__ import annotations

from unittest.mock import MagicMock

from urllib.robotparser import RobotFileParser

import pytest

from robots_util import can_fetch, robots_url_for_base


@pytest.mark.parametrize(
    "base,expected",
    [
        ("https://example.com/", "https://example.com/robots.txt"),
        ("https://example.com:8080/path", "https://example.com:8080/robots.txt"),
        ("http://sub.example.com", "http://sub.example.com/robots.txt"),
    ],
)
def test_robots_url_for_base(base, expected):
    assert robots_url_for_base(base) == expected


def test_can_fetch_with_none_parser():
    assert can_fetch(None, "https://example.com/page") is True


def test_can_fetch_delegates_to_parser():
    rp = MagicMock(spec=RobotFileParser)
    rp.can_fetch.return_value = True
    assert can_fetch(rp, "https://example.com/page") is True
    rp.can_fetch.assert_called_once_with("ScrapePortal/1.0 (+public research; respects robots.txt)", "https://example.com/page")


def test_can_fetch_swallows_exception():
    rp = MagicMock(spec=RobotFileParser)
    rp.can_fetch.side_effect = RuntimeError("broken")
    assert can_fetch(rp, "https://example.com/page") is False
