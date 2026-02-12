"""Tests for boost_mailing_list_tracker.services."""

from datetime import datetime, timezone

import pytest

from boost_mailing_list_tracker import services
from boost_mailing_list_tracker.models import MailingListMessage, MailingListName


# --- get_or_create_mailing_list_message ---


@pytest.mark.django_db
def test_get_or_create_mailing_list_message_creates_new(
    mailing_list_profile,
    default_list_name,
    sample_sent_at,
):
    """get_or_create_mailing_list_message creates new message and returns (message, True)."""
    msg, created = services.get_or_create_mailing_list_message(
        mailing_list_profile,
        msg_id="<new-msg@example.com>",
        sent_at=sample_sent_at,
        subject="Hello",
        list_name=default_list_name,
    )
    assert created is True
    assert msg.sender_id == mailing_list_profile.pk
    assert msg.msg_id == "<new-msg@example.com>"
    assert msg.subject == "Hello"
    assert msg.list_name == default_list_name
    assert msg.sent_at == sample_sent_at


@pytest.mark.django_db
def test_get_or_create_mailing_list_message_gets_existing(
    mailing_list_profile,
    default_list_name,
    sample_sent_at,
):
    """get_or_create_mailing_list_message returns existing and (message, False)."""
    services.get_or_create_mailing_list_message(
        mailing_list_profile,
        msg_id="<existing@example.com>",
        sent_at=sample_sent_at,
        subject="Original",
        list_name=default_list_name,
    )
    msg2, created2 = services.get_or_create_mailing_list_message(
        mailing_list_profile,
        msg_id="<existing@example.com>",
        sent_at=datetime(2024, 7, 1, tzinfo=timezone.utc),
        subject="Updated subject",
        list_name=default_list_name,
    )
    assert created2 is False
    assert msg2.subject == "Original"  # not updated


@pytest.mark.django_db
def test_get_or_create_mailing_list_message_empty_msg_id_raises(
    mailing_list_profile,
    default_list_name,
    sample_sent_at,
):
    """get_or_create_mailing_list_message raises ValueError for empty msg_id."""
    with pytest.raises(ValueError, match="msg_id must not be empty"):
        services.get_or_create_mailing_list_message(
            mailing_list_profile,
            msg_id="",
            sent_at=sample_sent_at,
            list_name=default_list_name,
        )
    with pytest.raises(ValueError, match="msg_id must not be empty"):
        services.get_or_create_mailing_list_message(
            mailing_list_profile,
            msg_id="   ",
            sent_at=sample_sent_at,
            list_name=default_list_name,
        )


@pytest.mark.django_db
def test_get_or_create_mailing_list_message_invalid_list_name_raises(
    mailing_list_profile,
    sample_sent_at,
):
    """get_or_create_mailing_list_message raises ValueError for invalid list_name."""
    with pytest.raises(ValueError, match="list_name must be one of"):
        services.get_or_create_mailing_list_message(
            mailing_list_profile,
            msg_id="<msg@example.com>",
            sent_at=sample_sent_at,
            list_name="invalid-list",
        )
    with pytest.raises(ValueError, match="list_name must be one of"):
        services.get_or_create_mailing_list_message(
            mailing_list_profile,
            msg_id="<msg2@example.com>",
            sent_at=sample_sent_at,
            list_name="",
        )


@pytest.mark.django_db
def test_get_or_create_mailing_list_message_strips_msg_id(
    mailing_list_profile,
    default_list_name,
    sample_sent_at,
):
    """get_or_create_mailing_list_message strips whitespace from msg_id."""
    msg, created = services.get_or_create_mailing_list_message(
        mailing_list_profile,
        msg_id="  <trimmed@example.com>  ",
        sent_at=sample_sent_at,
        list_name=default_list_name,
    )
    assert created is True
    assert msg.msg_id == "<trimmed@example.com>"


@pytest.mark.django_db
def test_get_or_create_mailing_list_message_all_list_names(
    mailing_list_profile,
    sample_sent_at,
):
    """get_or_create_mailing_list_message accepts all MailingListName values."""
    for i, list_value in enumerate(MailingListName):
        msg, created = services.get_or_create_mailing_list_message(
            mailing_list_profile,
            msg_id=f"<msg-{i}@example.com>",
            sent_at=sample_sent_at,
            list_name=list_value.value,
        )
        assert created is True
        assert msg.list_name == list_value.value


# --- delete_mailing_list_message ---


@pytest.mark.django_db
def test_delete_mailing_list_message_removes_from_db(
    mailing_list_profile,
    default_list_name,
    sample_sent_at,
):
    """delete_mailing_list_message deletes the message from database."""
    msg, _ = services.get_or_create_mailing_list_message(
        mailing_list_profile,
        msg_id="<to-delete@example.com>",
        sent_at=sample_sent_at,
        list_name=default_list_name,
    )
    pk = msg.pk
    services.delete_mailing_list_message(msg)
    assert not MailingListMessage.objects.filter(pk=pk).exists()


@pytest.mark.django_db
def test_delete_mailing_list_message_returns_none(
    mailing_list_profile,
    default_list_name,
    sample_sent_at,
):
    """delete_mailing_list_message returns None."""
    msg, _ = services.get_or_create_mailing_list_message(
        mailing_list_profile,
        msg_id="<return-none@example.com>",
        sent_at=sample_sent_at,
        list_name=default_list_name,
    )
    result = services.delete_mailing_list_message(msg)
    assert result is None


@pytest.mark.django_db
def test_delete_mailing_list_message_leaves_others(
    mailing_list_profile,
    default_list_name,
    sample_sent_at,
):
    """delete_mailing_list_message only removes the given message."""
    msg1, _ = services.get_or_create_mailing_list_message(
        mailing_list_profile,
        msg_id="<keep@example.com>",
        sent_at=sample_sent_at,
        list_name=default_list_name,
    )
    msg2, _ = services.get_or_create_mailing_list_message(
        mailing_list_profile,
        msg_id="<remove@example.com>",
        sent_at=sample_sent_at,
        list_name=default_list_name,
    )
    services.delete_mailing_list_message(msg2)
    assert MailingListMessage.objects.filter(msg_id="<keep@example.com>").exists()
    assert not MailingListMessage.objects.filter(msg_id="<remove@example.com>").exists()
