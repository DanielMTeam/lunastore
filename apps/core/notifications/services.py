from urllib.parse import urlsplit
import jwt
import time
import requests
import logging
from django.conf import settings

logger = logging.getLogger("core")

ICON_MAPPING = {
    'normal': 'system.png',
    'important': 'upgrade.png',
    'critical': 'error.png',
    'info': 'help.png',
    'success': 'ok.png'
}


class NotificationsUnavailable(Exception):
    pass


class NotificationService:

    # sign token method
    @staticmethod
    def generate_token(payload: dict) -> str:
        payload['exp'] = int(time.time()) + 3600  # 1 hour expiration
        return jwt.encode(
            payload,
            settings.LUNASPIRE_SECRET_KEY,
            algorithm='HS256')

    @classmethod
    def get_receive_token(cls, user_id: int) -> str:
        # generate gettkn for receiving notifications in frontend
        payload = {
            "type": "notify-get",
            "user_id": user_id
        }
        return cls.generate_token(payload)

    @staticmethod
    def _server_url():
        url = settings.LUNASPIRE_URL.strip().rstrip("/")
        if url.startswith("//"):
            return f"https:{url}"
        if not urlsplit(url).netloc:
            return f"https://{url}"
        return url

    @classmethod
    def send_notification(
            cls,
            user_id: int,
            title: str,
            content: str,
            meta: dict = None) -> bool:
        # generate sendtkn and push to lunaspire
        if meta is None:
            meta = {}

        # type of notification and icon mapping
        n_type = meta.get('type', 'normal')
        if 'icon' not in meta:
            meta['icon'] = ICON_MAPPING.get(n_type, 'system.png')

        payload = {
            "type": "notify-send",
            "title": title,
            "content": content,
            "user_id": user_id,
            "meta": meta
        }

        token = cls.generate_token(payload)

        try:
            # send PUT request to lunaspire
            response = requests.put(
                f"{cls._server_url()}/notifications/send",
                params={"token": token},
                timeout=5
            )
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            logger.warning("Failed to send notification (%s)", type(e).__name__)
            return False

    @classmethod
    def _receive_request(cls, method, path, user_id, **params):
        try:
            response = requests.request(
                method,
                f"{cls._server_url()}/notifications/{path}",
                params={"token": cls.get_receive_token(user_id), **params},
                timeout=3,
                allow_redirects=False,
            )
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict) and data.get("status") == "ok":
                    return data
        except (requests.RequestException, ValueError) as exc:
            logger.warning("LunaSpire notification request failed (%s)", type(exc).__name__)
            raise NotificationsUnavailable from exc
        logger.warning("LunaSpire notification request failed (HTTP %s)", response.status_code)
        raise NotificationsUnavailable

    @classmethod
    def list_notifications(cls, user_id: int, *, page: int, limit: int):
        return cls._receive_request("GET", "list", user_id, page=page, limit=limit)

    @classmethod
    def mark_all_read(cls, user_id: int):
        cls._receive_request("POST", "read-mark", user_id)

    @classmethod
    def get_notifications_meta(cls, user_id: int):
        try:
            data = cls.list_notifications(user_id, page=1, limit=1)
        except NotificationsUnavailable:
            return {'total': 0, 'total_unread': 0}
        return {'total': data.get('total', 0), 'total_unread': data.get('total_unread', 0)}
