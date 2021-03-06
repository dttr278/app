from flask import request, session, redirect, flash, url_for
from flask_login import login_user
from requests_oauthlib import OAuth2Session

from app import email_utils
from app.auth.base import auth_bp
from app.auth.views.login_utils import after_login
from app.config import GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, URL, DISABLE_REGISTRATION
from app.email_utils import can_be_used_as_personal_email, email_already_used
from app.extensions import db
from app.log import LOG
from app.models import User, SocialAuth
from app.utils import encode_url

_authorization_base_url = "https://github.com/login/oauth/authorize"
_token_url = "https://github.com/login/oauth/access_token"

# need to set explicitly redirect_uri instead of leaving the lib to pre-fill redirect_uri
# when served behind nginx, the redirect_uri is localhost... and not the real url
_redirect_uri = URL + "/auth/github/callback"


@auth_bp.route("/github/login")
def github_login():
    next_url = request.args.get("next")
    if next_url:
        redirect_uri = _redirect_uri + "?next=" + encode_url(next_url)
    else:
        redirect_uri = _redirect_uri

    github = OAuth2Session(
        GITHUB_CLIENT_ID, scope=["user:email"], redirect_uri=redirect_uri
    )
    authorization_url, state = github.authorization_url(_authorization_base_url)

    # State is used to prevent CSRF, keep this for later.
    session["oauth_state"] = state
    return redirect(authorization_url)


@auth_bp.route("/github/callback")
def github_callback():
    # user clicks on cancel
    if "error" in request.args:
        flash("Please use another sign in method then", "warning")
        return redirect("/")

    github = OAuth2Session(
        GITHUB_CLIENT_ID,
        state=session["oauth_state"],
        scope=["user:email"],
        redirect_uri=_redirect_uri,
    )
    token = github.fetch_token(
        _token_url,
        client_secret=GITHUB_CLIENT_SECRET,
        authorization_response=request.url,
    )

    # a dict with "name", "login"
    github_user_data = github.get("https://api.github.com/user").json()

    # return list of emails
    # {
    #     'email': 'abcd@gmail.com',
    #     'primary': False,
    #     'verified': True,
    #     'visibility': None
    # }
    emails = github.get("https://api.github.com/user/emails").json()

    # only take the primary email
    email = None

    for e in emails:
        if e.get("verified") and e.get("primary"):
            email = e.get("email")
            break

    if not email:
        LOG.error(f"cannot get email for github user {github_user_data} {emails}")
        flash(
            "Cannot get a valid email from Github, please another way to login/sign up",
            "error",
        )
        return redirect(url_for("auth.login"))

    email = email.lower()
    user = User.get_by(email=email)

    # create user
    if not user:
        if DISABLE_REGISTRATION:
            flash("Registration is closed", "error")
            return redirect(url_for("auth.login"))

        if not can_be_used_as_personal_email(email) or email_already_used(email):
            flash(f"You cannot use {email} as your personal inbox.", "error")
            return redirect(url_for("auth.login"))

        LOG.d("create github user")
        user = User.create(
            email=email.lower(), name=github_user_data.get("name") or "", activated=True
        )
        db.session.commit()
        login_user(user)
        email_utils.send_welcome_email(user)

        flash(f"Welcome to SimpleLogin {user.name}!", "success")

    if not SocialAuth.get_by(user_id=user.id, social="github"):
        SocialAuth.create(user_id=user.id, social="github")
        db.session.commit()

    # The activation link contains the original page, for ex authorize page
    next_url = request.args.get("next") if request.args else None

    return after_login(user, next_url)
