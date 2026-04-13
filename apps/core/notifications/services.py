import jwt, time, requests, logging
from django.conf import settings

logger = logging.getLogger("core")

ICON_MAPPING = {
    'normal': 'system.png',
    'important': 'upgrade.png',
    'critical': 'error.png',
    'info': 'help.png',
    'success': 'ok.png'
}



class NotificationService:

    # sign token method
    @staticmethod
    def generate_token(payload: dict) -> str:
        payload['exp'] = int(time.time()) + 3600 # 1 hour expiration
        return jwt.encode(payload, settings.LUNASPIRE_SECRET_KEY, algorithm='HS256')

    @classmethod
    def get_receive_token(cls, user_id: int) -> str:
        # generate gettkn for receiving notifications in frontend
        payload = {
            "type": "notify-get",
            "user": user_id
        }
        return cls.generate_token(payload)

    @classmethod
    def send_notification(cls, user_id: int, title: str, content: str, meta: dict = None) -> bool:
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
            "user": user_id,
            "meta": meta
        }

        token = cls.generate_token(payload)

        try:
            # send PUT request to lunaspire
            response = requests.put(
                f"{settings.LUNASPIRE_URL}/notifications/send",
                params={"token": token},
                timeout=5
            )
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            logger.info(f"Failed to send notification: {e}")
            return False
