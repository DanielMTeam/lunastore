import time
import uuid

import jwt
from django.conf import settings
from django.core.cache import cache

from apps.marketplace.services.access import application_role, can_manage_app
from apps.marketplace.services.distributions import can_submit_community_distribution

from .constants import ALLOWED_MIMES, PUB_UPLOAD_POLICIES


def issue_upload_token(user, object_id, mode, mimes, **options):
    guard = uuid.uuid4().hex
    cache.set(f"cdn_guard_{user.pk}_{guard}", {"object": object_id, "mode": mode}, timeout=3600)
    now = int(time.time())
    payload = {
        "type": "cdn-upload",
        "object": object_id,
        "user": str(user.pk),
        "guard": guard,
        "mode": mode,
        "accept": mimes,
        "iat": now,
        "exp": now + 3600,
        **options,
    }
    token = jwt.encode(payload, settings.LUNASPIRE_SECRET_KEY, algorithm="HS256")
    return {"upload_token": token, "guard": guard}


def issue_public_upload_token(user, target):
    policy = PUB_UPLOAD_POLICIES[target]
    return issue_upload_token(
        user, policy["obj"], "public", policy["mimes"], img_opts={"mw": policy["mw"], "mh": policy["mh"]},
    )


def can_upload_distribution(user, app):
    return (
        can_manage_app(app, user, "files")
        or user.is_staff
        or (application_role(app, user) is None and can_submit_community_distribution(app, user))
    )


def issue_private_upload_token(user, app):
    return issue_upload_token(user, str(app.pk), "private", ALLOWED_MIMES)
