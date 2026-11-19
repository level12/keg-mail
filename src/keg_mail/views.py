import hashlib
import hmac
import math
import time

import flask
import keg
from keg.db import db
from keg.web import BaseView


__all__ = [
    'LogStatusWebhook',
    'WebhookBase',
]


class WebhookBase(BaseView):
    signature_max_age_seconds = 5 * 60
    timestamp_future_tolerance_seconds = 60

    def verify(self, signing_key, data):
        if not isinstance(signing_key, str) or not signing_key.strip():
            return False
        if not isinstance(data, dict):
            return False

        signature = data.get('signature')
        event_data = data.get('event-data')
        if not isinstance(signature, dict) or not isinstance(event_data, dict):
            return False

        signature_fields = (
            signature.get('timestamp'),
            signature.get('token'),
            signature.get('signature'),
        )
        if not all(isinstance(value, str) and value for value in signature_fields):
            return False

        hmac_digest = hmac.new(
            key=signing_key.encode(),
            msg='{}{}'.format(signature['timestamp'], signature['token']).encode(),
            digestmod=hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(str(signature['signature']), str(hmac_digest)):
            return False

        try:
            signature_timestamp = float(signature['timestamp'])
            event_timestamp = float(event_data['timestamp'])
        except (KeyError, TypeError, ValueError):
            return False

        if not math.isfinite(signature_timestamp) or not math.isfinite(event_timestamp):
            return False

        now = time.time()
        if signature_timestamp < now - self.signature_max_age_seconds:
            return False
        if signature_timestamp > now + self.timestamp_future_tolerance_seconds:
            return False
        latest_event_timestamp = (
            min(signature_timestamp, now) + self.timestamp_future_tolerance_seconds
        )
        return event_timestamp <= latest_event_timestamp

    def post(self):
        data = flask.request.get_json(silent=True)

        signing_key = keg.current_app.config.get('MAIL_MAILGUN_WEBHOOK_KEY')
        if not self.verify(signing_key, data):
            flask.abort(403)

        self.process_event(data['event-data'])

        return 'OK', 200

    def process_event(self, event_data):
        pass


class LogStatusWebhook(WebhookBase):
    def process_event(self, event_data):
        try:
            keg.current_app.extensions['mail'].mailgun_update_message_status(event_data)
        except Exception:
            # Ensure any row locks are released
            db.session.rollback()
            raise
