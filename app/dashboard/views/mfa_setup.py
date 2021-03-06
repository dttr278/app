import pyotp
from flask import render_template, flash, redirect, url_for
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, validators

from app.dashboard.base import dashboard_bp
from app.extensions import db
from app.log import LOG


class OtpTokenForm(FlaskForm):
    token = StringField("Token", validators=[validators.DataRequired()])


@dashboard_bp.route("/mfa_setup", methods=["GET", "POST"])
@login_required
def mfa_setup():
    if current_user.enable_otp:
        flash("you have already enabled MFA", "warning")
        return redirect(url_for("dashboard.index"))

    otp_token_form = OtpTokenForm()

    if not current_user.otp_secret:
        LOG.d("Generate otp_secret for user %s", current_user)
        current_user.otp_secret = pyotp.random_base32()
        db.session.commit()

    totp = pyotp.TOTP(current_user.otp_secret)

    if otp_token_form.validate_on_submit():
        token = otp_token_form.token.data

        if totp.verify(token):
            current_user.enable_otp = True
            db.session.commit()
            flash("MFA has been activated", "success")
            return redirect(url_for("dashboard.index"))
        else:
            flash("Incorrect token", "warning")

    otp_uri = pyotp.totp.TOTP(current_user.otp_secret).provisioning_uri(
        name=current_user.email, issuer_name="SimpleLogin"
    )

    return render_template(
        "dashboard/mfa_setup.html", otp_token_form=otp_token_form, otp_uri=otp_uri
    )
