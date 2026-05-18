import logging
from typing import Optional
from uuid import UUID

import firebase_admin
from firebase_admin import credentials, messaging
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.device_token import DeviceToken

logger = logging.getLogger(__name__)

# Initialise Firebase Admin SDK once at module load
_firebase_app: Optional[firebase_admin.App] = None


def _get_firebase_app() -> firebase_admin.App:
    global _firebase_app
    if _firebase_app is None:
        if not settings.FIREBASE_SERVICE_ACCOUNT_PATH:
            raise RuntimeError("FIREBASE_SERVICE_ACCOUNT_PATH not set in config")
        cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_PATH)
        _firebase_app = firebase_admin.initialize_app(cred)
    return _firebase_app


class FCMService:
    def send_to_user(
        self,
        db: Session,
        user_id: UUID,
        title: str,
        body: str,
        data: Optional[dict] = None,
    ) -> int:
        """Send a notification to all registered devices for a user. Returns number of successful sends."""
        tokens = (
            db.query(DeviceToken.token)
            .filter(DeviceToken.user_id == user_id)
            .all()
        )
        if not tokens:
            return 0
        token_list = [t.token for t in tokens]
        return self._send_multicast(db, token_list, title, body, data or {})

    def send_to_token(
        self,
        db: Session,
        token: str,
        title: str,
        body: str,
        data: Optional[dict] = None,
    ) -> bool:
        """Send a notification to a single device token."""
        _get_firebase_app()
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data={k: str(v) for k, v in (data or {}).items()},
            token=token,
            android=messaging.AndroidConfig(priority="high"),
        )
        try:
            messaging.send(message)
            return True
        except messaging.UnregisteredError:
            self._remove_token(db, token)
            return False
        except Exception as e:
            logger.error(f"FCM send_to_token failed: {e}")
            return False

    def _send_multicast(
        self,
        db: Session,
        tokens: list[str],
        title: str,
        body: str,
        data: dict,
    ) -> int:
        _get_firebase_app()
        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            data={k: str(v) for k, v in data.items()},
            tokens=tokens,
            android=messaging.AndroidConfig(priority="high"),
        )
        try:
            response = messaging.send_each_for_multicast(message)
        except Exception as e:
            logger.error(f"FCM multicast failed: {e}")
            return 0

        # Clean up stale tokens
        for idx, result in enumerate(response.responses):
            if not result.success:
                err = result.exception
                if isinstance(err, (messaging.UnregisteredError, messaging.SenderIdMismatchError)):
                    self._remove_token(db, tokens[idx])
                else:
                    logger.warning(f"FCM failed for token index {idx}: {err}")

        logger.info(f"FCM multicast: {response.success_count}/{len(tokens)} delivered")
        return response.success_count

    def _remove_token(self, db: Session, token: str) -> None:
        db.query(DeviceToken).filter(DeviceToken.token == token).delete()
        db.commit()
        logger.info(f"Removed stale FCM token")


fcm_service = FCMService()
