"""
SMS / WhatsApp backends (stub). Implement Twilio, Africa's Talking, or WhatsApp
Cloud API subclasses when ready; register via NOTIFICATION_SMS_BACKEND in settings.
"""
import logging

logger = logging.getLogger(__name__)


class BaseSmsBackend:
    def send(self, to_e164: str, body: str) -> bool:
        raise NotImplementedError


class NullSmsBackend(BaseSmsBackend):
    """No-op backend for Phase 8; logs intent only."""

    def send(self, to_e164: str, body: str) -> bool:
        logger.info('SMS disabled; would send to %s: %s', to_e164, body[:80])
        return False
