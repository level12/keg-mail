import flask

from keg_mail.views import (
    LogStatusWebhook as LogStatusWebhookBase,
    WebhookBase,
)

km_blueprint = flask.Blueprint('keg_mail', __name__)


class NoOpWebhook(WebhookBase):
    blueprint = km_blueprint
    url = '/noop-webhook'


class LogStatusWebhook(LogStatusWebhookBase):
    blueprint = km_blueprint
    url = '/log-status-webhook'
