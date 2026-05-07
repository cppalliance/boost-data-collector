"""Direct tests for boost_mailing_list_tracker.email_formatter."""

from boost_mailing_list_tracker.email_formatter import (
    format_email,
    _deobfuscate_address,
    _extract_list_name,
    _extract_sender,
    _extract_url_tail_id,
    _normalize_sent_at,
    _normalize_one,
    _to_text,
)


def test_extract_url_tail_id():
    assert _extract_url_tail_id("") == ""
    assert _extract_url_tail_id("https://x/y/z") == "z"
    assert _extract_url_tail_id("plain") == "plain"


def test_extract_list_name_patterns():
    url = "https://lists.boost.org/list/foo/thread/abc/"
    assert _extract_list_name(url) == "foo"
    assert _extract_list_name("", "archives@lists.boost.org") != ""
    assert _extract_list_name("no-match") == ""


def test_deobfuscate_address():
    assert _deobfuscate_address("") == ""
    assert "@" in _deobfuscate_address("user (a) lists.boost.org")


def test_extract_sender_variants():
    addr, name = _extract_sender(
        {"from": '"Alice" <alice@example.com>', "sender_address": "", "sender_name": ""}
    )
    assert addr.endswith("example.com")
    assert name


def test_normalize_sent_at_rfc2822():
    raw = {"date": "Sat, 03 Apr 2010 18:32:00 +0200"}
    out = _normalize_sent_at(raw)
    assert out is not None
    assert "2010" in out


def test_format_email_shapes():
    assert format_email([]) == []
    assert format_email("x") == []
    one = format_email([{"msg_id": "a", "subject": "S"}])
    assert len(one) == 1
    assert one[0]["msg_id"] == "a"

    threaded = format_email(
        {
            "thread_info": {"thread_id": "tid"},
            "messages": [{"message_id": "m1", "subject": "Hi"}],
        }
    )
    assert threaded[0]["thread_id"] == "tid"


def test_to_text_non_string_and_none():
    assert _to_text(None) == ""
    assert _to_text(42) == "42"


def test_extract_list_name_from_to_header():
    assert (
        _extract_list_name("Discussion <boost-users@lists.boost.org>")
        == "boost-users@lists.boost.org"
    )


def test_deobfuscate_address_patterns():
    assert _deobfuscate_address("user [at] lists.boost.org") == "user@lists.boost.org"
    assert _deobfuscate_address("person AT example.com") == "person@example.com"
    assert (
        _deobfuscate_address("somebody at lists.boost.org")
        == "somebody@lists.boost.org"
    )
    assert _deobfuscate_address("u(at)v.org") == "u@v.org"


def test_extract_sender_nested_dict_email_and_display_name():
    addr, name = _extract_sender(
        {
            "sender": {"email": "nested@example.com", "display_name": "Nested"},
            "sender_address": "",
            "sender_name": "",
        }
    )
    assert addr == "nested@example.com"
    assert name == "Nested"


def test_extract_sender_early_return_when_address_and_name_present():
    addr, name = _extract_sender(
        {"sender": {"address": "a@b.com", "name": "Quick"}, "from": "ignored <z@z.com>"}
    )
    assert addr == "a@b.com"
    assert name == "Quick"


def test_normalize_sent_at_prefers_sent_at_over_date():
    out = _normalize_sent_at(
        {"sent_at": "iso-only", "date": "Sat, 03 Apr 2010 18:32:00 +0200"}
    )
    assert out == "iso-only"


def test_normalize_sent_at_invalid_rfc2822_returns_raw():
    out = _normalize_sent_at({"date": "not-valid-for-parse"})
    assert out == "not-valid-for-parse"


def test_normalize_sent_at_naive_rfc2822_returns_isoformat():
    raw = {"date": "Sat, 03 Apr 2010 18:32:00"}
    out = _normalize_sent_at(raw)
    assert out is not None
    assert "2010-04-03" in out


def test_format_email_single_message_dict_fallback():
    out = format_email({"msg_id": "<single@example.com>", "subject": "S"})
    assert len(out) == 1
    assert out[0]["msg_id"] == "<single@example.com>"


def test_format_email_non_dict_thread_info_coerced_to_empty():
    out = format_email(
        {
            "thread_info": "not-a-dict",
            "messages": [{"message_id": "mid", "subject": "Hi"}],
        }
    )
    assert len(out) == 1


def test_normalize_one_accepts_thread_info_url_for_list():
    thread = {
        "url": "https://lists.boost.org/archives/api/list/boost@lists.boost.org/thread/x/"
    }
    row = {"message_id": "m1", "subject": "S"}
    normalized = _normalize_one(row, thread_info=thread)
    assert normalized["list_name"] == "boost@lists.boost.org"
