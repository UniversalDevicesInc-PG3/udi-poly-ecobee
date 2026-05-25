"""PG3 notice timestamp helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from node_funcs import notice_html_with_timestamp, notice_text_with_timestamp, notice_timestamp_text


def test_notice_timestamp_text_is_iso_like():
    dt = datetime(2026, 5, 25, 16, 21, 0, tzinfo=timezone.utc)
    assert notice_timestamp_text(dt) == '2026-05-25 16:21:00+00:00'


def test_notice_html_with_timestamp_prepends_code_block():
    dt = datetime(2026, 5, 25, 16, 21, 0, tzinfo=timezone.utc)
    html = notice_html_with_timestamp('<p>body</p>', now=dt)
    assert '<b>Timestamp:</b>' in html
    assert '<code>2026-05-25 16:21:00+00:00</code>' in html
    assert html.endswith('<p>body</p>')


def test_notice_text_with_timestamp_escapes_plain_text():
    dt = datetime(2026, 5, 25, 16, 21, 0, tzinfo=timezone.utc)
    html = notice_text_with_timestamp('a < b', now=dt)
    assert '<code>2026-05-25 16:21:00+00:00</code>' in html
    assert '<p>a &lt; b</p>' in html
