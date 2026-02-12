"""Tests for boost_mailing_list_tracker models."""

import pytest
from django.db import IntegrityError
from model_bakery import baker

from boost_mailing_list_tracker.models import MailingListMessage, MailingListName


# --- MailingListName ---


def test_mailing_list_name_choices():
    """MailingListName has expected list choices."""
    assert MailingListName.BOOST_ANNOUNCE.value == "boost-announce@lists.boost.org"
    assert MailingListName.BOOST_USERS.value == "boost-users@lists.boost.org"
    assert MailingListName.BOOST.value == "boost@lists.boost.org"
    assert len(MailingListName) == 3


# --- MailingListMessage ---


@pytest.mark.django_db
def test_mailing_list_message_links_sender(mailing_list_profile, default_list_name, sample_sent_at):
    """MailingListMessage is linked to MailingListProfile as sender."""
    from boost_mailing_list_tracker import services

    msg, _ = services.get_or_create_mailing_list_message(
        mailing_list_profile,
        msg_id="<msg-001@example.com>",
        sent_at=sample_sent_at,
        list_name=default_list_name,
    )
    assert msg.sender_id == mailing_list_profile.pk
    assert msg.sender == mailing_list_profile


@pytest.mark.django_db
def test_mailing_list_message_stores_msg_id_and_list_name(
    mailing_list_profile,
    default_list_name,
    sample_sent_at,
):
    """MailingListMessage stores msg_id and list_name."""
    from boost_mailing_list_tracker import services

    msg, _ = services.get_or_create_mailing_list_message(
        mailing_list_profile,
        msg_id="<unique-msg@lists.boost.org>",
        sent_at=sample_sent_at,
        list_name=default_list_name,
    )
    assert msg.msg_id == "<unique-msg@lists.boost.org>"
    assert msg.list_name == default_list_name


@pytest.mark.django_db
def test_mailing_list_message_stores_optional_fields(
    mailing_list_profile,
    default_list_name,
    sample_sent_at,
):
    """MailingListMessage stores parent_id, thread_id, subject, content."""
    from boost_mailing_list_tracker import services

    msg, _ = services.get_or_create_mailing_list_message(
        mailing_list_profile,
        msg_id="<with-fields@example.com>",
        sent_at=sample_sent_at,
        parent_id="<parent@example.com>",
        thread_id="thread-1",
        subject="Test subject",
        content="Body text",
        list_name=default_list_name,
    )
    assert msg.parent_id == "<parent@example.com>"
    assert msg.thread_id == "thread-1"
    assert msg.subject == "Test subject"
    assert msg.content == "Body text"


@pytest.mark.django_db
def test_mailing_list_message_has_created_at(
    mailing_list_profile,
    default_list_name,
    sample_sent_at,
):
    """MailingListMessage has created_at."""
    from boost_mailing_list_tracker import services

    msg, _ = services.get_or_create_mailing_list_message(
        mailing_list_profile,
        msg_id="<created-at@example.com>",
        sent_at=sample_sent_at,
        list_name=default_list_name,
    )
    assert msg.created_at is not None


@pytest.mark.django_db
def test_mailing_list_message_ordering():
    """MailingListMessage Meta ordering is -sent_at."""
    assert MailingListMessage._meta.ordering == ["-sent_at"]


@pytest.mark.django_db
def test_mailing_list_message_str_with_subject(
    mailing_list_profile,
    default_list_name,
    sample_sent_at,
):
    """MailingListMessage __str__ uses subject (truncated) when present."""
    from boost_mailing_list_tracker import services

    msg, _ = services.get_or_create_mailing_list_message(
        mailing_list_profile,
        msg_id="<str-subject@example.com>",
        sent_at=sample_sent_at,
        subject="A short subject",
        list_name=default_list_name,
    )
    assert "A short subject" in str(msg)
    assert default_list_name in str(msg)


@pytest.mark.django_db
def test_mailing_list_message_str_fallback_to_msg_id(
    mailing_list_profile,
    default_list_name,
    sample_sent_at,
):
    """MailingListMessage __str__ uses msg_id when subject empty."""
    from boost_mailing_list_tracker import services

    msg, _ = services.get_or_create_mailing_list_message(
        mailing_list_profile,
        msg_id="<no-subject@example.com>",
        sent_at=sample_sent_at,
        subject="",
        list_name=default_list_name,
    )
    assert "<no-subject@example.com>" in str(msg)


@pytest.mark.django_db
def test_mailing_list_message_msg_id_unique(
    mailing_list_profile,
    default_list_name,
    sample_sent_at,
):
    """MailingListMessage msg_id is unique."""
    from boost_mailing_list_tracker import services

    services.get_or_create_mailing_list_message(
        mailing_list_profile,
        msg_id="<duplicate@example.com>",
        sent_at=sample_sent_at,
        list_name=default_list_name,
    )
    with pytest.raises(IntegrityError):
        baker.make(
            "boost_mailing_list_tracker.MailingListMessage",
            sender=mailing_list_profile,
            msg_id="<duplicate@example.com>",
            list_name=default_list_name,
            sent_at=sample_sent_at,
        )
