from flask import g
from flask import jsonify, request
from flask_cors import cross_origin

from app.api.base import api_bp, verify_api_key
from app.config import MAX_NB_EMAIL_FREE_PLAN
from app.dashboard.views.custom_alias import verify_prefix_suffix
from app.extensions import db
from app.log import LOG
from app.models import GenEmail, AliasUsedOn, User
from app.utils import convert_to_id


@api_bp.route("/alias/custom/new", methods=["POST"])
@cross_origin()
@verify_api_key
def new_custom_alias():
    """
    Create a new custom alias
    Input:
        alias_prefix, for ex "www_groupon_com"
        alias_suffix, either .random_letters@simplelogin.co or @my-domain.com
        optional "hostname" in args
        optional "note"
    Output:
        201 if success
        409 if the alias already exists

    """
    user: User = g.user
    if not user.can_create_new_alias():
        LOG.d("user %s cannot create any custom alias", user)
        return (
            jsonify(
                error="You have reached the limitation of a free account with the maximum of "
                f"{MAX_NB_EMAIL_FREE_PLAN} aliases, please upgrade your plan to create more aliases"
            ),
            400,
        )

    user_custom_domains = [cd.domain for cd in user.verified_custom_domains()]
    hostname = request.args.get("hostname")

    data = request.get_json()
    if not data:
        return jsonify(error="request body cannot be empty"), 400

    alias_prefix = data.get("alias_prefix", "").strip()
    alias_suffix = data.get("alias_suffix", "").strip()
    note = data.get("note")
    alias_prefix = convert_to_id(alias_prefix)

    if not verify_prefix_suffix(user, alias_prefix, alias_suffix, user_custom_domains):
        return jsonify(error="wrong alias prefix or suffix"), 400

    full_alias = alias_prefix + alias_suffix
    if GenEmail.get_by(email=full_alias):
        LOG.d("full alias already used %s", full_alias)
        return jsonify(error=f"alias {full_alias} already exists"), 409

    gen_email = GenEmail.create(
        user_id=user.id, email=full_alias, mailbox_id=user.default_mailbox_id, note=note
    )
    db.session.commit()

    if hostname:
        AliasUsedOn.create(gen_email_id=gen_email.id, hostname=hostname)
        db.session.commit()

    return jsonify(alias=full_alias), 201
