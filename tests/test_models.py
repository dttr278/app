from uuid import UUID

import arrow
import pytest

from app.config import EMAIL_DOMAIN, MAX_NB_EMAIL_FREE_PLAN
from app.extensions import db
from app.models import generate_email, User, GenEmail


def test_generate_email(flask_client):
    email = generate_email()
    assert email.endswith("@" + EMAIL_DOMAIN)

    with pytest.raises(ValueError):
        UUID(email.split("@")[0], version=4)

    email_uuid = generate_email(scheme=2)
    assert UUID(email_uuid.split("@")[0], version=4)


def test_profile_picture_url(flask_client):
    user = User.create(
        email="a@b.c", password="password", name="Test User", activated=True
    )
    db.session.commit()

    assert user.profile_picture_url() == "http://sl.test/static/default-avatar.png"


def test_suggested_emails_for_user_who_cannot_create_new_alias(flask_client):
    # make sure user is not in trial
    user = User.create(
        email="a@b.c",
        password="password",
        name="Test User",
        activated=True,
        trial_end=None,
    )

    db.session.commit()

    # make sure user runs out of quota to create new email
    for i in range(MAX_NB_EMAIL_FREE_PLAN):
        GenEmail.create_new(user=user, prefix="test")
    db.session.commit()

    suggested_email, other_emails = user.suggested_emails(website_name="test")

    # the suggested email is chosen from existing GenEmail
    assert GenEmail.get_by(email=suggested_email)

    # all other emails are generated emails
    for email in other_emails:
        assert GenEmail.get_by(email=email)


def test_gen_email_create_random(flask_client):
    user = User.create(
        email="a@b.c", password="password", name="Test User", activated=True
    )
    db.session.commit()

    alias = GenEmail.create_new_random(user)
    assert alias.email.endswith(EMAIL_DOMAIN)
