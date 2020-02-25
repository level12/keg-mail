import hashlib
import hmac

import flask
import keg
from keg.db import db
from keg.web import BaseView


__all__ = [
    'WebhookBase',
    'LogStatusWebhook',
]


class WebhookBase(BaseView):
    def verify(self, signing_key, data):
        signature = data['signature']

        hmac_digest = hmac.new(
            key=signing_key.encode(),
            msg=('{}{}'.format(signature['timestamp'], signature['token'])).encode(),
            digestmod=hashlib.sha256).hexdigest()
        return hmac.compare_digest(str(signature['signature']), str(hmac_digest))

    def post(self):
        data = flask.request.json

        signing_key = keg.current_app.config['MAIL_MAILGUN_WEBHOOK_KEY']
        if not self.verify(signing_key, data):
            flask.abort(403)

        self.process_event(data['event-data'])

        return 'OK', 200

    def process_event(self, event_data):
        pass


class LogStatusWebhook(WebhookBase):
    def process_event(self, event_data):
        try:
            keg.current_app.extensions['mail'].update_message_status(event_data)
        except Exception:
            # Ensure any row locks are released
            db.session.rollback()
            raise
